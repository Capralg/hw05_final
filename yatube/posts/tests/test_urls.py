from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.core.cache import cache

from http import HTTPStatus

from posts.models import Post, Group

User = get_user_model()


class StaticURLTests(TestCase):
    def test_static_page(self):
        static_pages = [
            '/', '/about/author/', '/about/tech/',
        ]
        for page in static_pages:
            response = self.client.get(page)
            self.assertEqual(response.status_code, HTTPStatus.OK)


class PostURLTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='Vasya')
        cls.group = Group.objects.create(
            slug='test-slug',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='012345678901234567890',
            group=cls.group,
        )

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(
            User.objects.get(username='Vasya')
        )

    def test_urls_uses_correct_template(self):
        """Несоответсвие шаблону"""
        template_url_names = {
            'posts/index.html': '/',
            'posts/group_list.html': f'/group/{PostURLTests.group.slug}/',
            'posts/profile.html': f'/profile/{PostURLTests.post.author}/',
            'posts/post_detail.html': f'/posts/{PostURLTests.post.pk}/',
            'posts/create.html': f'/posts/{PostURLTests.post.id}/edit/',
        }
        cache.clear()
        for template, adress in template_url_names.items():
            with self.subTest():
                response = self.authorized_client.get(adress)
                self.assertTemplateUsed(
                    response, template,
                    msg_prefix=f'{template} + {adress}'
                )

    def test_unexisting_page(self):
        response = self.client.get('/about/Vasya/')
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_unauthorised_user(self):
        response = self.client.get('/create/')
        self.assertEqual(response.status_code, HTTPStatus.FOUND)

    def test_not_author(self):
        self.user = User.objects.create_user(username='HasNoName')
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        response = self.authorized_client.get(
            f'/posts/{PostURLTests.post.id}/edit/'
        )
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
