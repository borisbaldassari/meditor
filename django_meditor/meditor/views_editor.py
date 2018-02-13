import functools
import json

from datetime import datetime
from time import time

from django.http import HttpResponse
from django.template import loader

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from meditor.meditor_export import fetch_model

from django import shortcuts
from django.http import Http404

from meditor.meditor_import import feed_models
from meditor.models import Attribute, DataSourceType, Goal, Metric, MetricData, QualityModel

from . import forms_editor
from . import data


class EditorState():

    def __init__(self, qmodel_name=None, goals=[], attributes=[],
                 metric_datas=[], form=None):
        self.qmodel_name = qmodel_name
        self.goals = goals
        self.attributes = attributes
        self.metric_datas = metric_datas

        if form:
            # The form includes the state not chnaged to be propagated
            goals_state = form.cleaned_data['goals_state']
            attributes = form.cleaned_data['attributes_state']
            metric_datas = form.cleaned_data['metric_datas_state']

            if not self.qmodel_name:
                self.qmodel_name = form.cleaned_data['qmodel_name_state']
            if not self.goals:
                self.goals = [goals_state] if goals_state else []
            if not self.attributes:
                self.attributes = [attributes] if attributes else []
            if not self.metric_datas:
                self.metric_datas = [metric_datas] if metric_datas else []

    def is_empty(self):
        return not (self.qmodel_name or self.goals or self.attributes or
                    self.metric_datas)

    def initial_state(self):
        """ State to be filled in the forms so it is propagated

        The state needs to be serialized so it can be used in
        forms fields.
        """

        initial = {
            'qmodel_name_state': self.qmodel_name,
            'goals_state': ";".join(self.goals),
            'attributes_state': ";".join(self.attributes),
            "metric_datas_state": ";".join([str(repo_view_id) for repo_view_id in self.metric_datas])
        }

        return initial

def perfdata(func):
    @functools.wraps(func)
    def decorator(*args, **kwargs):
        task_init = time()
        data = func(*args, **kwargs)
        print("%s: %0.3f sec" % (func, time() - task_init))
        return data
    return decorator


def return_error(message):

    template = loader.get_template('meditor/error.html')
    context = {"alert_message": message}
    render_error = template.render(context)
    return HttpResponse(render_error)


def select_goal(request, template, context=None):
    if request.method == 'POST':
        form = forms_editor.GoalsForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            goals = [name]
            state = EditorState(goals=goals, form=form)
            if context:
                context.update(build_forms_context(state))
            else:
                context = build_forms_context(state)
            return shortcuts.render(request, template, context)
        else:
            # TODO: Show error
            raise Http404
    # if a GET (or any other method) we'll create a blank form
    else:
        # TODO: Show error
        return shortcuts.render(request, template, build_forms_context())


@perfdata
def select_qmodel(request, template, context=None):
    if request.method == 'POST':
        form = forms_editor.QualityModelsForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            if not name:
                # TODO: Show error when qmodel name is empty
                return shortcuts.render(request, template, build_forms_context())
            # Select and qmodel reset the state. Don't pass form=form
            state = build_forms_context(EditorState(qmodel_name=name))
            if context:
                context.update(state)
            else:
                context = build_forms_context(EditorState(qmodel_name=name))
            return shortcuts.render(request, template, context)
        else:
            # Ignore when the empty option is selected
            return shortcuts.render(request, template, build_forms_context())
    # if a GET (or any other method) we'll create a blank form
    else:
        # TODO: Show error
        return shortcuts.render(request, template, build_forms_context())


@perfdata
def build_forms_context(state=None):
    """ Get all forms to be shown in the editor """
    qmodel_form = forms_editor.QualityModelsForm(state=state)
    add_qmodel_form = forms_editor.QualityModelForm(state=state)
    goals_form = forms_editor.GoalsForm(state=state)
    goal_form = forms_editor.GoalForm(state=state)
    goal_remove_form = forms_editor.GoalForm(state=state)
    attribute_form = forms_editor.AttributeForm(state=state)
    attributes_form = forms_editor.AttributesForm(state=state)
    metric_datas_form = forms_editor.MetricsDataForm(state=state)
    metric_data_form = forms_editor.MetricDataForm(state=state)

    if state:
        qmodel_form.initial['name'] = state.qmodel_name
        if state.goals:
            goals_form.initial['name'] = state.goals[0]
            goal_remove_form = forms_editor.GoalForm(state=state)
            goal_remove_form.initial['goal_name'] = state.goals[0]
        if state.attributes:
            attributes_form.initial['name'] = state.attributes[0]

    context = {"qmodels_form": qmodel_form,
               "qmodel_form": add_qmodel_form,
               "goals_form": goals_form,
               "goal_form": goal_form,
               "goal_remove_form": goal_remove_form,
               "attribute_form": attribute_form,
               "attributes_form": attributes_form,
               "metric_datas_form": metric_datas_form,
               "metric_data_form": metric_data_form
               }
    return context

##
# editor page methods
##

@perfdata
def editor(request):
    """ Shows the Meditor Editor """

    context = build_forms_context()

    return shortcuts.render(request, 'meditor/editor.html', context)


def editor_select_qmodel(request):
    return select_qmodel(request, "meditor/editor.html")


def add_qmodel(request):

    if request.method == 'POST':
        form = forms_editor.QualityModelForm(request.POST)
        if form.is_valid():
            qmodel_name = form.cleaned_data['qmodel_name']

            try:
                qmodel_orm = QualityModel.objects.get(name=qmodel_name)
            except QualityModel.DoesNotExist:
                qmodel_orm = QualityModel(name=qmodel_name)
                qmodel_orm.save()

            # Select and qmodel reset the state. Don't pass form=form
            return shortcuts.render(request, 'meditor/editor.html',
                                    build_forms_context(EditorState(qmodel_name=qmodel_name)))
        else:
            # TODO: Show error
            print("FORM errors", form.errors)
            raise Http404
    # if a GET (or any other method) we'll create a blank form
    else:
        # TODO: Show error
        return shortcuts.render(request, 'meditor/editor.html', build_forms_context())


def add_metric_data(request):
    if request.method == 'POST':
        form = forms_editor.MetricDataForm(request.POST)
        if form.is_valid():
            metric = form.cleaned_data['metric']
            params = form.cleaned_data['params']
            attribute = form.cleaned_data['attribute']
            # Don't support multiselect in goals yet
            goal = form.cleaned_data['goals_state']
            # Adding a new metric view
            try:
                attribute_orm = Attribute.objects.get(name=attribute)
            except Attribute.DoesNotExist:
                attribute_orm = Attribute(name=attribute)
                attribute_orm.save()

            # Try to find a metric already created
            try:
                metric_orm = Metric.objects.get(name=metric, attribute=attribute_orm)
            except Metric.DoesNotExist:
                # Create a new metric
                metric_orm = Metric(name=metric, attribute=attribute_orm)
                metric_orm.save()
            # Try to find a metric view already created
            try:
                metric_data_orm = MetricData.objects.get(params=params, metric=metric_orm)
            except MetricData.DoesNotExist:
                metric_data_orm = MetricData(params=params,
                                                     metric=metric_orm)
                metric_data_orm.save()
            # If there is a goal defined, add the metric view to the goal
            if goal:
                goal_orm = Goal.objects.get(name=goal)
                goal_orm.metric_datas.add(metric_data_orm)
                goal_orm.save()

            metric_data_orm.save()

            form.cleaned_data['metric_datas_state'] = []
            state = EditorState(form=form)
            return shortcuts.render(request, 'meditor/editor.html',
                                    build_forms_context(state))
        else:
            # TODO: Show error
            print(form.errors)
            raise Http404
    # if a GET (or any other method) we'll create a blank form
    else:
        # TODO: Show error
        return shortcuts.render(request, 'meditor/editor.html', build_forms_context())


def update_metric_data(request):
    if request.method == 'POST':
        form = forms_editor.MetricDataForm(request.POST)

        if form.is_valid():
            metric_data_id = form.cleaned_data['metric_data_id']
            metric = form.cleaned_data['metric']
            params = form.cleaned_data['params']
            attribute = form.cleaned_data['attribute']

            metric_data_orm = MetricData.objects.get(id=metric_data_id)

            try:
                metric_orm = Metric.objects.get(name=metric)
                metric_data_orm.metric = metric_orm
            except Metric.DoesNotExist:
                # Create a new metric
                attribute_orm = Attribute.objects.get(name=attribute)
                metric_orm = Metric(name=metric, attribute=attribute_orm)
                metric_orm.save()

            metric_data_orm.metric = metric_orm
            metric_data_orm.params = params

            metric_data_orm.save()

            state = EditorState(metric_datas=[metric_data_id], form=form)
            return shortcuts.render(request, 'meditor/editor.html',
                                    build_forms_context(state))
        else:
            # TODO: Show error
            print(form.errors)
            raise Http404
    # if a GET (or any other method) we'll create a blank form
    else:
        # TODO: Show error
        return shortcuts.render(request, 'meditor/editor.html', build_forms_context())


def remove_metric_data(request):
    if request.method == 'POST':
        form = forms_editor.MetricDataForm(request.POST)
        if form.is_valid():
            if form.cleaned_data['metric_data_id']:
                metric_data_id = int(form.cleaned_data['metric_data_id'])
                MetricData.objects.get(id=metric_data_id).delete()
            # Clean from the state the removed metric view
            form.cleaned_data['metric_datas_state'] = []
            return shortcuts.render(request, 'meditor/editor.html',
                                    build_forms_context(EditorState(form=form)))
        else:
            # TODO: Show error
            print(form.errors)
            raise Http404
    # if a GET (or any other method) we'll create a blank form
    else:
        # TODO: Show error
        return shortcuts.render(request, 'meditor/editor.html', build_forms_context())


def select_metric_data(request):
    if request.method == 'POST':
        form = forms_editor.MetricsDataForm(request.POST)
        if form.is_valid():
            metric_data_id = int(form.cleaned_data['id'])
            state = EditorState(form=form, metric_datas=[metric_data_id])
            return shortcuts.render(request, 'meditor/editor.html',
                                    build_forms_context(state))
        else:
            # TODO: Show error
            raise Http404
    # if a GET (or any other method) we'll create a blank form
    else:
        # TODO: Show error
        return shortcuts.render(request, 'meditor/editor.html', build_forms_context())


def add_attribute(request):

    if request.method == 'POST':
        form = forms_editor.AttributeForm(request.POST)
        if form.is_valid():
            qmodel_name = form.cleaned_data['qmodel_name_state']
            qmodel_orm = None
            goal_name = form.cleaned_data['goals_state']
            goal_orm = None
            if qmodel_name:
                qmodel_orm = QualityModel.objects.get(name=qmodel_name)
                goals_orm = qmodel_orm.goals.all()
                qmodel_orm.save()

            attribute_name = form.cleaned_data['attribute_name']
            attribute_orm = Attribute(name=attribute_name)
            attribute_orm.save()

            return shortcuts.render(request, 'meditor/editor.html',
                                    build_forms_context(EditorState(form=form)))
        else:
            # TODO: Show error
            raise Http404
    # if a GET (or any other method) we'll create a blank form
    else:
        # TODO: Show error
        return shortcuts.render(request, 'meditor/editor.html', build_forms_context())


def select_attribute(request):
    if request.method == 'POST':
        form = forms_editor.AttributesForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            attributes = [name] if name else []

            return shortcuts.render(request, 'meditor/editor.html',
                                    build_forms_context(EditorState(form=form, attributes=attributes)))
        else:
            # TODO: Show error
            raise Http404
    # if a GET (or any other method) we'll create a blank form
    else:
        # TODO: Show error
        return shortcuts.render(request, 'meditor/editor.html', build_forms_context())


def editor_select_goal(request):
    return select_goal(request, "meditor/editor.html")


def remove_goal(request):
    if request.method == 'POST':
        form = forms_editor.GoalForm(request.POST)
        if form.is_valid():
            goal_name = form.cleaned_data['goal_name']
            Goal.objects.get(name=goal_name).delete()
            return shortcuts.render(request, 'meditor/editor.html', build_forms_context())
        else:
            # TODO: Show error
            print("remove_goal", form.errors)
            raise Http404
    # if a GET (or any other method) we'll create a blank form
    else:
        # TODO: Show error
        return shortcuts.render(request, 'meditor/editor.html', build_forms_context())


def add_goal(request):
    if request.method == 'POST':
        form = forms_editor.GoalForm(request.POST)
        if form.is_valid():
            qmodel_name = form.cleaned_data['qmodel_name_state']
            qmodel_orm = None
            goal_name = form.cleaned_data['goal_name']
            goal_orm = Goal(name=goal_name)
            goal_orm.save()
            if qmodel_name:
                qmodel_orm = QualityModel.objects.get(name=qmodel_name)
                qmodel_orm.goals.add(goal_orm)
                qmodel_orm.save()
            context = EditorState(goals=[goal_name], form=form)
            return shortcuts.render(request, 'meditor/editor.html',
                                    build_forms_context(context))
        else:
            # TODO: Show error
            raise Http404
    # if a GET (or any other method) we'll create a blank form
    else:
        # TODO: Show error
        return shortcuts.render(request, 'meditor/editor.html', build_forms_context())


def find_goal_metric_datas(goal):

    data = {"metric_datas": []}

    try:
        goal_orm = Goal.objects.get(name=goal)
        metric_datas_orm = goal_orm.metric_datas.all()
        for view in metric_datas_orm:
            data['metric_datas'].append({
                "id": view.id,
                "name": view.metric.name,
                "params": view.params,
                "type": view.metric.attribute.name
            })
    except Goal.DoesNotExist:
        print('Can not find goal', goal)

    return data


def find_goal_attributes(goal):
    data = {"attributes": []}
    already_added_attributes = []

    try:
        goal_orm = Goal.objects.get(name=goal)
        metric_datas = goal_orm.metric_datas.all()
        for metric_data_orm in metric_datas:
            if metric_data_orm.metric.attribute.id in already_added_attributes:
                continue
            already_added_attributes.append(metric_data_orm.metric.attribute.id)
            data['attributes'].append({
                "id": metric_data_orm.metric.attribute.id,
                "name": metric_data_orm.metric.attribute.name
            })
    except Goal.DoesNotExist:
        print('Can not find goal', goal)

    return data


def find_goals(qmodel=None):
    data = {"goals": []}

    try:
        if qmodel:
            qmodel_orm = QualityModel.objects.get(name=qmodel)
            goals_orm = qmodel_orm.goals.all()
        else:
            goals_orm = Goal.objects.all()
        for goal in goals_orm:
            data['goals'].append({
                "id": goal.id,
                "name": goal.name
            })
    except QualityModel.DoesNotExist:
        print('Can not find qmodel', qmodel)

    return data


def import_from_file(request):

    if request.method == "POST":
        myfile = request.FILES["imported_file"]
        qmodel = request.POST["name"]
        cur_dt = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        file_name = "%s_%s.json" % (qmodel, cur_dt)
        fpath = '.imported/' + file_name  # FIXME Define path where all these files must be saved
        save_path = default_storage.save(fpath, ContentFile(myfile.read()))

        task_init = time()
        try:
            (ngoals, nrepos) = load_goals(save_path, qmodel)
        except Exception:
            error_msg = "File %s couldn't be imported." % myfile.name
            return return_error(error_msg)

        print("Total loading time ... %.2f sec", time() - task_init)
        print("Goals loaded", ngoals)
        print("Metrics loaded", nrepos)

    return editor_select_qmodel(request)


def export_to_file(request, qmodel=None):

    if (request.method == "GET") and (not qmodel):
        return editor(request)

    if request.method == "POST":
        qmodel = request.POST["name"]

    file_name = "goals_%s.json" % qmodel
    task_init = time()
    try:
        goals = fetch_goals(qmodel)
    except (QualityModel.DoesNotExist, Exception):
        error_msg = "Goals from qmodel \"%s\" couldn't be exported." % qmodel
        if request.method == "POST":
            # If request comes from web UI and fails, return error page
            return return_error(error_msg)
        else:
            # If request comes as a GET request, return HTTP 404: Not Found
            return HttpResponse(status=404)

    print("Total loading time ... %.2f sec", time() - task_init)
    if goals:
        goals_json = json.dumps(goals, indent=True, sort_keys=True)
        response = HttpResponse(goals_json, content_type="application/json")
        response['Content-Disposition'] = 'attachment; filename=' + file_name
        return response
    else:
        error_msg = "There are no goals to export"
        return return_error(error_msg)

    return editor(request)
