from django.db import models

import gm2m

from ..app.models import Project


class Links(models.Model):

    class Meta:
        app_label = 'extrevrel'

    related_objects = gm2m.GM2MField(Project, related_name='related_links')
