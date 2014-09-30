from tastypie.resources import ModelResource
from tastypie.authorization import Authorization
from tastypie import fields

from .models import ProjectSheet, ProjectSheetTemplate, ProjectSheetSuggestedItem, ProjectSheetQuestion
from projects.api import ProjectResource
from projects.models import Project
from django.core.urlresolvers import reverse
from tastypie.constants import ALL_WITH_RELATIONS


class ProjectSheetTemplateResource(ModelResource):
    class Meta:
        queryset = ProjectSheetTemplate.objects.all()
        allowed_methods = ['post', 'get']
        resource_name = 'projectsheettemplate'
        authorization = Authorization()
        always_return_data = True
        filtering = { 
            'id' : ('exact', )
        }
        
    def dehydrate(self, bundle):
        bundle.data["questions"] = []
        for question in bundle.obj.projectsheetquestion_set.all():
            bundle.data["questions"].append(question.text)
        return bundle
    
class ProjectSheetQuestionResource(ModelResource):
    class Meta:
        queryset = ProjectSheetQuestion.objects.all()
        allowed_methods = ['post', 'get']
        resource_name = 'projectsheetquestion'
        authorization = Authorization()
        
    def hydrate(self, bundle):
        bundle.obj.template = ProjectSheetTemplate.objects.get(id=bundle.data["template_id"])
        return bundle

class ProjectSheetSuggestedItemResource(ModelResource):
    class Meta:
        queryset = ProjectSheetSuggestedItem.objects.all()
        allowed_methods = ['get', 'patch']
        resource_name = 'projectsheetsuggesteditem'
        authorization = Authorization()

class ProjectSheetResource(ModelResource):
    project = fields.ToOneField(ProjectResource, 'project')
    template = fields.ToOneField(ProjectSheetTemplateResource, 'template')
    
    class Meta:
        queryset = ProjectSheet.objects.all()
        allowed_methods = ['get', 'post', 'put']
        default_format = "application/json"
        resource_name = 'projectsheet'
        authorization = Authorization()
        always_return_data = True
        filtering = { 
            'project' : ALL_WITH_RELATIONS,
            'template' : ALL_WITH_RELATIONS,
        }
        
    def dehydrate(self, bundle):
        bundle.data["items"] = []
        for item in bundle.obj.projectsheetsuggesteditem_set.all().order_by("question__order"):
            bundle.data["items"].append(reverse('api_dispatch_detail', kwargs={'api_name' : 'v0', #FIXME : hardcoded
                                                                 'resource_name' : 'projectsheetsuggesteditem',
                                                                 'pk' :item.id}))
        return bundle
    
    def hydrate(self, bundle):
        bundle.obj.project = Project.objects.get(id=bundle.data["project_id"])
        bundle.obj.template = ProjectSheetTemplate.objects.get(id=bundle.data["template_id"])
        return bundle