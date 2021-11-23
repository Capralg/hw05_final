import os
import shutil
import tempfile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.core.cache import cache

from ..forms import PostForm
from ..models import Group, Post, Comment, Follow

User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostCreateFormTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='Vasya')
        cls.user02 = User.objects.create_user(username='NeVasya')
        cls.group = Group.objects.create(
            title='Тестовый заголовок',
            slug='test_slug',
            description='Тестовое описание'
        )
        cls.post = Post.objects.create(
            text='Тестовый текст',
            author=cls.user,
            group=cls.group
        )
        cls.post02 = Post.objects.create(
            text='Тестовый текст02',
            author=cls.user,
            group=cls.group
        )
        cls.form = PostForm()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(
            User.objects.get(username='Vasya')
        )

    def test_create_post(self):
        """Валидная форма создает запись в Post."""
        post_count = Post.objects.count()
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif'
        )
        form_data = {
            'text': PostCreateFormTests.post.text,
            'group': PostCreateFormTests.group.pk,
            'image': uploaded,
        }
        response = self.authorized_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )
        latest_post = Post.objects.latest('id')
        self.assertRedirects(response, reverse(
            'posts:profile', args=[self.user.username]))
        self.assertEqual(Post.objects.count(), post_count + 1)
        self.assertEqual(latest_post.text, form_data['text'])
        self.assertEqual(latest_post.group.pk, form_data['group'])
        self.assertEqual(
            os.path.basename(latest_post.image.name),
            form_data['image'].name
        )

    def test_edit_post(self):
        """Валидная форма редактирует запись в Post."""
        post_count = Post.objects.count()

        form_data = {
            'text': 'Тестовый текст03',
            'group': PostCreateFormTests.group.pk,
        }
        response = self.authorized_client.post(
            reverse('posts:post_edit', args=[self.post.pk]),
            data=form_data,
            follow=True
        )
        self.assertRedirects(response, reverse(
            'posts:post_detail', args=[self.post.pk]))
        self.assertEqual(Post.objects.count(), post_count)
        self.assertTrue(
            Post.objects.filter(
                text=form_data['text'],
                author=PostCreateFormTests.user,
                group=form_data['group']
            ).exists()
        )

    def test_create_post_by_anonim(self):
        """Проверка создния записи анонимом"""
        post_count = Post.objects.count()
        form_data = {
            'text': PostCreateFormTests.post.text,
            'group': PostCreateFormTests.group.pk,
        }
        response = self.client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )

        self.assertRedirects(response, '/auth/login/?next=/create/')
        self.assertEqual(Post.objects.count(), post_count)

    def test_edit_post_by_anonim(self):
        """Проверка редактирования записи анонимом"""
        post_count = Post.objects.count()
        form_data = {
            'text': 'Тестовый текст04',
            'group': PostCreateFormTests.group.pk,
        }
        post = PostCreateFormTests.post
        response = self.client.post(
            reverse('posts:post_edit', args=[self.post.pk]),
            data=form_data,
            follow=True
        )
        self.assertRedirects(
            response, f'/auth/login/?next=/posts/{self.post.pk}/edit/')
        self.assertEqual(Post.objects.count(), post_count)
        self.assertEqual(post.text, self.post.text)
        self.assertEqual(post.group, self.post.group)

    def test_create_comment_by_anonim(self):
        """Проверка создния комментария анонимом"""
        comment_count = Comment.objects.count()
        form_data = {
            'text': 'Текст комментария № 01',
        }
        response = self.client.post(
            reverse('posts:add_comment', args=[self.post.pk]),
            data=form_data,
            follow=True
        )
        self.assertRedirects(response, '/auth/login/?next=/posts/1/comment/')
        self.assertEqual(Comment.objects.count(), comment_count)

    def test_insert_new_comment(self):
        form_data = {
            'text': 'Текст комментария № 02',
        }
        response = self.authorized_client.post(
            reverse('posts:add_comment',
                    kwargs={'post_id': PostCreateFormTests.post.pk}),
            data=form_data,
            follow=True
        )
        self.assertRedirects(
            response,
            reverse(
                'posts:post_detail',
                kwargs={'post_id': PostCreateFormTests.post.pk}
            )
        )

        response = self.authorized_client.get(
            reverse(
                'posts:post_detail',
                kwargs={'post_id': PostCreateFormTests.post.pk}
            )
        )
        comment = Comment.objects.filter(
            author=PostCreateFormTests.user,
            text=form_data['text']
        )
        self.assertEqual(comment[0] in response.context['comments'], True)

    def test_cache_of_posts_on_home_page(self):
        """Проверяем, что посты на главной странице кэшируются"""
        response = self.authorized_client.get(reverse('posts:index'))
        cached_page_01 = response.content
        self.post02.delete()
        response = self.authorized_client.get(reverse('posts:index'))
        cached_page_02 = response.content
        self.assertEqual(cached_page_01, cached_page_02)
        cache.clear()
        response = self.authorized_client.get(reverse('posts:index'))
        self.assertNotEqual(cached_page_01, response.content)

    def test_authorized_user_follow(self):
        """Авторизованный пользователь может подписаться и отписаться"""
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user02)
        response = Follow.objects.filter(user=self.user).count()
        self.client.get(
            reverse('posts:profile_follow', args=[self.user.username]))
        self.assertEqual(response, 0)
        self.authorized_client.get(
            reverse('posts:profile_follow', args=[self.user.username]))
        self.assertEqual(response, 0)
        response = Follow.objects.filter(user=self.user02).count()
        self.authorized_client.get(
            reverse('posts:profile_follow', args=[self.user02.username]))
        self.assertEqual(response, 1)
        self.authorized_client.get(
            reverse('posts:profile_follow', args=[self.user02.username]))
        response = Follow.objects.filter(user=self.user02).count()
        self.assertEqual(response, 1)

    def test_authorized_user_follow(self):
        """Авторизованный пользователь может подписаться и отписаться"""
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user02)
        response = Follow.objects.filter(user=self.user).count()
        self.client.get(
            reverse('posts:profile_follow', args=[self.user.username]))
        self.assertEqual(response, 0)
        self.authorized_client.get(
            reverse('posts:profile_follow', args=[self.user.username]))
        self.assertEqual(response, 0)
        response = Follow.objects.filter(user=self.user02).count()
        self.authorized_client.get(
            reverse('posts:profile_follow', args=[self.user02.username]))
        self.assertEqual(response, 1)
        self.authorized_client.get(
            reverse('posts:profile_follow', args=[self.user02.username]))
        response = Follow.objects.filter(user=self.user02).count()
        self.assertEqual(response, 1)
