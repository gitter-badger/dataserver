# -*- encoding: utf-8 -*-
from django.conf.urls import url
from django.contrib.auth.models import User, Group
from django.contrib.auth import authenticate, logout
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from tastypie.http import HttpUnauthorized, HttpForbidden

from tastypie import fields
from tastypie.authentication import Authentication, BasicAuthentication, ApiKeyAuthentication
from tastypie.authorization import DjangoAuthorization, Authorization
from tastypie.models import ApiKey, create_api_key
from tastypie.resources import ModelResource
from tastypie.utils import trailing_slash

from dataserver.authorization import GuardianAuthorization

from guardian.shortcuts import assign_perm


class UserResource(ModelResource):
    class Meta:
        queryset = User.objects.exclude(pk=-1) # Exclude anonymous user
        detail_uri_name = 'username'
        allowed_methods = ['get', 'post']
        resource_name = 'account/user'
        authentication = Authentication()
        authorization = Authorization()
        fields = ['username', 'first_name', 'last_name', 'groups']

    groups = fields.ToManyField('accounts.api.GroupResource', 'groups', null=True, full=False)

    def dehydrate(self, bundle):
        bundle.data['mugshot'] = bundle.obj.profile.mugshot
        bundle.data['groups'] = [{"id" : group.id, "name":group.name} for group in bundle.obj.groups.all()]
        #bundle.data['first_name'] = bundle.obj.user.first_name
        #bundle.data['last_name'] = bundle.obj.user.last_name
        return bundle
    
        
    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/login%s$" %
                (self._meta.resource_name, trailing_slash()),
                self.wrap_view('login'), name="api_login"),
            url(r"^(?P<resource_name>%s)/login/google%s$" %
                (self._meta.resource_name, trailing_slash()),
                self.wrap_view('login_google'), name="api_login_google"),
            url(r'^(?P<resource_name>%s)/logout%s$' %
                (self._meta.resource_name, trailing_slash()),
                self.wrap_view('logout'), name='api_logout'),
        ]

    def login_google(self, request, **kwargs):
        """
        Given an oauth2 google token, check it and if ok, return or
        create a user.
        """
        import httplib, urllib
        import simplejson
        
        self.method_check(request, allowed=['post'])        
        data = self.deserialize(request, request.body, format=request.META.get('CONTENT_TYPE', 'application/json'))

        oauth_token = data.get('access_token', '')
        conn = httplib.HTTPSConnection("www.googleapis.com")
        conn.request("GET", "/oauth2/v1/userinfo?access_token=%s" % oauth_token)
        response = conn.getresponse()

        user = None
        if response.reason == "OK":
            data = simplejson.loads(response.read())
            if data['verified_email']:
                user, created = User.objects.get_or_create(username=data['email'],
                                                           email=data['email'],
                                                           first_name=data['given_name'],
                                                           last_name=data['family_name'])

        return self.login_to_apikey(request, user)
        
    def login(self, request, **kwargs):
        """
        Login a user against a username/password.
        Return an API Key that's going to be used for the following requests
        """
        self.method_check(request, allowed=['post'])

        data = self.deserialize(request, request.body, format=request.META.get('CONTENT_TYPE', 'application/json'))

        username = data.get('username', '')
        password = data.get('password', '')

        user = authenticate(username=username, password=password)        
        return self.login_to_apikey(request, user)


    def login_to_apikey(self, request, user):
        if user:
            if user.is_active:
                # login(request, user)

                try:
                    key = ApiKey.objects.get(user=user)
                except ApiKey.DoesNotExist:
                    return self.create_response(
                        request, {
                            'success': False,
                            'reason': 'missing key',
                        },
                        HttpForbidden,
                    )

                ret = self.create_response(request, {
                    'success': True,
                    'username': user.username,
                    'key': key.key,
                })

                return ret
            else:
                return self.create_response(
                    request, {
                        'success': False,
                        'reason': 'disabled',   
                    },
                    HttpForbidden,
                )
        else:
            return self.create_response(
                request, {
                    'success': False,
                    'reason': 'invalid login',
                    'skip_login_redir': True,
                },
                HttpUnauthorized,
            )

    def logout(self, request, **kwargs):
        self.method_check(request, allowed=['get'])
        if request.user and request.user.is_authenticated():
            logout(request)
            return self.create_response(request, {'success': True})
        else:
            return self.create_response(request, {'success': False}, HttpUnauthorized)


class GroupResource(ModelResource):
    class Meta:
        queryset = Group.objects.all()
        resource_name = 'account/group'
        authentication = ApiKeyAuthentication()
        authorization = GuardianAuthorization(
            create_permission_code="add_group",
            view_permission_code="change_group",
            update_permission_code="change_group",
            delete_permission_code="delete_group"
        )

    users = fields.ToManyField(UserResource, 'user_set', full=True)

    
# Create API key for every new user
models.signals.post_save.connect(create_api_key, sender=User)

# Add CMS permissions to every new user 
@receiver(post_save, sender=User)
def assign_CMS_editor_perm_to_groups(sender, instance, created, *args, **kwargs):
    if created:
        assign_perm("cms.view_page", user_or_group=instance)
        assign_perm("cms.change_page", user_or_group=instance)
        assign_perm("cms.publish_page", user_or_group=instance)
        assign_perm("cms.add_title", user_or_group=instance)
        assign_perm("cms.change_title", user_or_group=instance)
        assign_perm("cms.delete_title", user_or_group=instance)
        assign_perm("cms_background_images.add_backgroundimagesplugin", user_or_group=instance)
        assign_perm("cms_background_images.change_backgroundimagesplugin", user_or_group=instance)
        assign_perm("cms_background_images.delete_backgroundimagesplugin", user_or_group=instance)
        assign_perm("cms_carto.add_cartoplugin", user_or_group=instance)
        assign_perm("cms_carto.change_cartoplugin", user_or_group=instance)
        assign_perm("cms_carto.delete_cartoplugin", user_or_group=instance)
        assign_perm("cms_news.add_newsentry", user_or_group=instance)
        assign_perm("cms_news.change_newsentry", user_or_group=instance)
        assign_perm("cms_news.delete_newsentry", user_or_group=instance)
        assign_perm("cms_news.add_newsplugin", user_or_group=instance)
        assign_perm("cms_news.change_newsplugin", user_or_group=instance)
        assign_perm("cms_news.delete_newsplugin", user_or_group=instance)
        assign_perm("djangocms_picture.add_picture", user_or_group=instance)
        assign_perm("djangocms_picture.change_picture", user_or_group=instance)
        assign_perm("djangocms_picture.delete_picture", user_or_group=instance)
        assign_perm("djangocms_text_ckeditor.add_text", user_or_group=instance)
        assign_perm("djangocms_text_ckeditor.change_text", user_or_group=instance)
        assign_perm("djangocms_text_ckeditor.delete_text", user_or_group=instance)
        
        


