# Copyright (c) 2014 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from oslo.db.sqlalchemy.utils import InvalidSortKey
from wsme.exc import ClientSideError

from storyboard.db.api import base as api_base
from storyboard.db import models
from storyboard.openstack.common.gettextutils import _  # noqa


def project_get(project_id):
    return api_base.entity_get(models.Project, project_id)


def project_get_by_name(name):
    query = api_base.model_query(models.Project, api_base.get_session())
    return query.filter_by(name=name).first()


def project_get_all(marker=None, limit=None, sort_field=None, sort_dir=None,
                    project_group_id=None, **kwargs):
    # Sanity checks, in case someone accidentally explicitly passes in 'None'
    if not sort_field:
        sort_field = 'id'
    if not sort_dir:
        sort_dir = 'asc'

    # Construct the query
    query = project_build_query(project_group_id=project_group_id,
                                **kwargs)

    try:
        query = api_base.paginate_query(query=query,
                                        model=models.Project,
                                        limit=limit,
                                        sort_keys=[sort_field],
                                        marker=marker,
                                        sort_dir=sort_dir)
    except InvalidSortKey:
        raise ClientSideError(_("Invalid sort_field [%s]") % (sort_field,),
                              status_code=400)
    except ValueError as ve:
        raise ClientSideError(_("%s") % (ve,), status_code=400)

    # Execute the query
    return query.all()


def project_get_count(project_group_id=None, **kwargs):
    # Construct the query
    query = project_build_query(project_group_id=project_group_id,
                                **kwargs)

    return query.count()


def project_create(values):
    return api_base.entity_create(models.Project, values)


def project_update(project_id, values):
    return api_base.entity_update(models.Project, project_id, values)


def project_build_query(project_group_id, **kwargs):
    # Construct the query
    query = api_base.model_query(models.Project)

    if project_group_id:
        query = query.join(models.Project.project_groups) \
            .filter(models.ProjectGroup.id == project_group_id)

    # Sanity check on input parameters
    query = api_base.apply_query_filters(query=query, model=models.Project,
                                         **kwargs)

    return query
