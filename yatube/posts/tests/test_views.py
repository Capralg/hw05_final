import os
import shutil
import tempfile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django import forms
from django.core.cache import cache

from posts.models import Post, Group
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostURLTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='Vasya')
        cls.user2 = User.objects.create_user(username='Sasha')
        cls.group = Group.objects.create(
            slug='test-slug',
        )
        cls.group2 = Group.objects.create(
            slug='test-slug2',
        )
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
        cls.image = uploaded
        cls.post_list = []
        for i in range(1, 13):
            cls.post_list.append(
                Post(
                    id=i,
                    text=f'Тестовый пост{i}',
                    author=cls.user,
                    group=cls.group,
                    image=cls.image,
                )
            )
        cls.post_list.append(
            Post(
                text='Тестовый пост13',
                author=cls.user2,
                group=cls.group2,
                image=cls.image,
            )
        )
        Post.objects.bulk_create(cls.post_list)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(
            User.objects.get(username='Vasya')
        )

    def test_urls_uses_correct_template(self):
        """Несоответсвие шаблону"""
        template_url_names = {
            f"{reverse('posts:index')}": 'posts/index.html',
            f"{reverse('posts:group_list', args=[self.group.slug])}":
            'posts/group_list.html',
            f"{reverse('posts:post_create')}": 'posts/create.html',
            f"{reverse('posts:post_edit', args=[self.post_list[0].pk])}":
            'posts/create.html',
            f"{reverse('posts:post_detail', args=[self.post_list[0].pk])}":
            'posts/post_detail.html',
            f"{reverse('posts:profile', args=[self.user.username])}":
            'posts/profile.html',
        }
        cache.clear()
        for adress, template in template_url_names.items():
            with self.subTest():
                response = self.authorized_client.get(adress)
                self.assertTemplateUsed(
                    response, template,
                    msg_prefix=f'{adress}'
                )

    def test_index_first_page_contains_ten_records(self):
        cache.clear()
        response = self.client.get(reverse('posts:index'))
        self.assertEqual(
            len(response.context['page_obj']),
            response.context['page_obj'].paginator.per_page
        )

    def test_index_second_page_contains_three_records(self):
        response = self.client.get(reverse('posts:index') + '?page=2')
        tot_pag_num = response.context['page_obj'].end_index()
        fst_pag_num = response.context['page_obj'].paginator.per_page
        scd_pag_num = tot_pag_num - fst_pag_num
        self.assertEqual(
            len(response.context['page_obj']),
            scd_pag_num,
        )

    def test_group_list_first_page_contains_ten_records(self):
        response = self.client.get(
            reverse('posts:group_list', args=[self.group.slug])
        )
        self.assertEqual(
            len(response.context['page_obj']),
            response.context['page_obj'].paginator.per_page
        )

    def test_group_list_second_page_contains_three_records(self):
        response = self.client.get(
            reverse('posts:group_list', args=[self.group.slug]) + '?page=2'
        )
        tot_pag_num = response.context['page_obj'].end_index()
        fst_pag_num = response.context['page_obj'].paginator.per_page
        scd_pag_num = tot_pag_num - fst_pag_num
        self.assertEqual(
            len(response.context['page_obj']),
            scd_pag_num,
        )

    def test_profile_first_page_contains_ten_records(self):
        response = self.client.get(
            reverse('posts:profile', args=[self.user.username])
        )
        self.assertEqual(
            len(response.context['page_obj']),
            response.context['page_obj'].paginator.per_page
        )

    def test_profile_second_page_contains_three_records(self):
        response = self.client.get(
            reverse('posts:profile', args=[self.user.username]) + '?page=2'
        )
        tot_pag_num = response.context['page_obj'].end_index()
        fst_pag_num = response.context['page_obj'].paginator.per_page
        scd_pag_num = tot_pag_num - fst_pag_num
        self.assertEqual(
            len(response.context['page_obj']),
            scd_pag_num
        )

    def test_post_detail_page_show_correct_context(self):
        """Шаблон group_list сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse('posts:post_detail', args=[self.post_list[0].pk]))
        first_object = response.context['post']
        post_text = first_object.text
        post_author = first_object.author.username
        post_group = first_object.group
        post_image = first_object.image
        self.assertEqual(post_text, self.post_list[0].text)
        self.assertEqual(post_author, 'Vasya')
        self.assertEqual(post_group, self.group)
        self.assertEqual(os.path.basename(post_image.name), self.image.name)

    def test_create_page_show_correct_context(self):
        """Шаблон create_page сформирован с правильным контекстом."""
        response = self.authorized_client.get(reverse('posts:post_create'))
        forms_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField,
        }

        for value, expected in forms_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)

    def test_edit_page_show_correct_context(self):
        """Шаблон edit_page сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse('posts:post_edit', args=[self.post_list[0].pk]))
        forms_fields = {
            'text': forms.fields.CharField,
            'group': forms.fields.ChoiceField,
        }

        for value, expected in forms_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)

    def test_index_page_show_correct_context(self):
        """Шаблон index показывает картинки."""
        cache.clear()
        response = self.authorized_client.get(
            reverse('posts:index'))
        objects = response.context['page_obj']
        post_image = objects[0].image
        self.assertNotEqual(post_image.name, '')

    def test_profile_page_show_correct_context(self):
        """Шаблон profile показывает картинки."""
        response = self.authorized_client.get(
            reverse('posts:profile', args=[self.user.username]))
        objects = response.context['page_obj']
        post_image = objects[0].image
        self.assertNotEqual(post_image.name, '')

    def test_group_list_page_show_correct_context(self):
        """Шаблон group_list показывает картинки."""
        response = self.authorized_client.get(
            reverse('posts:group_list', args=[self.group.slug]))
        objects = response.context['page_obj']
        post_image = objects[0].image
        self.assertNotEqual(post_image.name, '')

    def test_post_detail_page_show_correct_context(self):
        """Шаблон post_detail показывает картинки."""
        response = self.authorized_client.get(
            reverse('posts:post_detail', args=[self.post_list[0].pk]))
        objects = response.context['post']
        post_image = objects.image
        self.assertNotEqual(post_image.name, '')
