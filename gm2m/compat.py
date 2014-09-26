from copy import copy
from bisect import bisect
import inspect

import django
from django.db import models
from django.db.models.options import Options
from django.db.models.fields import related
from django.utils import six

try:
    from django.contrib.contenttypes.fields import ForeignObjectRel
except ImportError:
    # Django < 1.7
    from django.contrib.contenttypes.generic import GenericRel

    if django.VERSION < (1, 6):
        class ForeignObjectRel(GenericRel):
            def __init__(self, field, to):
                super(ForeignObjectRel, self).__init__(to)
                self.field = field
    else:
        ForeignObjectRel = GenericRel


class RelatedObject(related.RelatedObject):
    if django.VERSION < (1, 6):
        def related_query_name(self):
            return self.field.related_query_name()

        def m2m_db_table(self):
            try:
                return self.rel.through.db_table
            except AttributeError:
                return None

        def __lt__(self, ro):
            # for python 3.3
            return id(self) < id(ro)


if django.VERSION < (1, 6):

    # We need to make sure that queryset related methods are available
    # under the old and new denomination (it is taken care of by
    # django.utils.deprecation.RenameMethodBase in Django >= 1.6)
    # A Metaclass is needed for that purpose

    class GetQSetRenamer(type):
        # inspired from django 1.6's RenameMethodsBase

        renamed_methods = (
            ('get_query_set', 'get_queryset'),
            ('get_prefetch_query_set', 'get_prefetch_queryset')
        )

        def __new__(cls, name, bases, attrs):
            new_class = super(GetQSetRenamer, cls).__new__(cls, name,
                                                           bases, attrs)

            for base in inspect.getmro(new_class):
                for renamed_method in cls.renamed_methods:
                    old_method_name = renamed_method[0]
                    old_method = base.__dict__.get(old_method_name)
                    new_method_name = renamed_method[1]
                    new_method = base.__dict__.get(new_method_name)

                    if not new_method and old_method:
                        # Define the new method if missing
                        setattr(base, new_method_name, old_method)
                    elif not old_method and new_method:
                        # Define the old method if missing
                        setattr(base, old_method_name, new_method)

            return new_class

    mngr_base = six.with_metaclass(GetQSetRenamer, models.Manager)
else:
    mngr_base = models.Manager


class Manager(mngr_base):

    if django.VERSION < (1, 6):

        __metaclass__ = GetQSetRenamer

        def _mk_core_filters_norel(self, instance):
            self.core_filters = {'%s__pk' % self.query_field_name:
                                 instance._get_pk_val()}

        def _prefetch_qset_query_norel(self, instances):
            return models.Q(**{'%s_id__in' % self.field_names['src']:
                set(obj._get_pk_val() for obj in instances)})

    else:

        def _mk_core_filters_norel(self, instance):
            source_field = self.through._meta.get_field(
                               self.field_names['src'])
            self.source_related_fields = source_field.related_fields
            for __, rh_field in self.source_related_fields:
                key = '%s__%s' % (self.query_field_name, rh_field.name)
                self.core_filters[key] = getattr(instance,
                                                 rh_field.attname)

        def _prefetch_qset_query_norel(self, instances):
            query = {}
            for lh_field, rh_field in self.source_related_fields:
                query['%s__in' % lh_field.name] = \
                    set(getattr(obj, rh_field.attname)
                        for obj in instances)
            return models.Q(**query)


def get_model_name(x):
    opts = x if isinstance(x, Options) else x._meta
    try:
        return opts.model_name
    except AttributeError:
        # Django < 1.6
        return opts.object_name.lower()


def add_related_field(opts, field):
    if django.VERSION < (1, 6):
        # hack to enable deletion cascading
        from .relations import GM2MRel
        f = copy(field)
        f.rel = GM2MRel(field, field.rel.to)
        opts.local_many_to_many.insert(bisect(opts.local_many_to_many, f), f)
        for attr in ('_m2m_cache', '_name_map'):
            try:
                delattr(opts, attr)
            except AttributeError:
                pass
    else:
        opts.add_virtual_field(field)


def get_local_related_fields(fk):
    try:
        return fk.local_related_fields
    except AttributeError:  # Django < 1.6
        return (fk,)


def get_foreign_related_fields(fk):
    try:
        return fk.foreign_related_fields
    except AttributeError:  # Django < 1.6
        return (fk.rel.get_related_field(),)


def is_swapped(model):
    # falls back to False for Django < 1.6
    return getattr(model._meta, 'swapped', False)