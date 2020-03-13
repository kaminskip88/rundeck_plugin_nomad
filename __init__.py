import json
import time
import nomad
import base64
from functools import partial
from rundeck_plugin_common import RundeckPlugin, RundeckPluginError
from .job_model import jobspec, groupspec, taskspec, templatespec


class NomadEvaluationException(RundeckPluginError):
    """ Evaluation failure """


class NomadAllocationException(RundeckPluginError):
    """ Allocation failure """


class RundeckPluginNomad(RundeckPlugin):
    def __init__(self, *args, **kwargs):
        super(RundeckPluginNomad, self).__init__(*args, **kwargs)
        self.log = self.logger(__name__)

    def nomad_connect(self, *args, **kwargs):
        self.nomad = nomad.Nomad(kwargs)

    def __evaluate(self, id):
        while True:
            status = self.nomad.evaluation.get_evaluation(id)['Status']
            self.log.debug('Evaluation {} status: {}'.format(id, status))
            if status == 'pending':
                time.sleep(5)
                continue
            elif status == 'complete':
                if self.nomad.evaluation.get_allocations(id):
                    return self.nomad.evaluation.get_allocations(id)
                else:
                    raise NomadEvaluationException
            else:
                raise NomadEvaluationException

    def __monitor(self, id):
        __offset = [0, 0]
        while True:
            alloc = self.nomad.allocation.get_allocation(id)
            status = alloc['ClientStatus']
            self.log.debug('Allocation {} status: {}'.format(id, status))
            for i, log_type in enumerate(['stderr', 'stdout']):
                __offset[i] = self.__logs(id, __offset[i], log_type)
            if status == 'pending':
                time.sleep(2)
                continue
            elif status == 'running':
                time.sleep(2)
                continue
            elif status == 'complete':
                return True
            else:
                raise NomadAllocationException

    # This generator uses json.JSONDecoder.raw_decode() to read
    # multiple json objects from string
    def __json_parser(self, text, decoder=json.JSONDecoder()):
        while text:
            try:
                result, index = decoder.raw_decode(text)
                yield result
                text = text[index:].lstrip()
            except ValueError:
                break

    def __logs(self, id, offset, log_type):
        try:
            logs_json = self.nomad.client.stream_logs.stream(
                    id, self.task_name, log_type, follow=False, offset=offset
            )
            self.log.debug(logs_json)
        except nomad.api.exceptions.URLNotFoundNomadException:
            logs_json = None
        if logs_json:
            # When requesting nginx log stream for very long log entries,
            # it can return multiple json objects in as single response.
            # see __json_parser method for more details
            for log in self.__json_parser(logs_json):
                self.print(base64.b64decode(log.get('Data', '')).decode('ascii'))
                offset = log.get('Offset', 0)
        return offset

    def __filter_alloc(self, allocations):
        return next(
            (i for i in allocations if i['TaskGroup'] == self.group_name),
            None)

    def __variafy(self, list):
        list[0] = '${{{0}}}'.format(list[0])
        return list

    def nomad_run(
        self,
        env={},
        cpu=200,
        ram=512,
        dc=['dc1'],
        disk=100,
        config={},
        name=None,
        user=None,
        priority=50,
        artifacts=[],
        templates=[],
        driver='exec',
        constraints=[],
        task_name='exec',
        eval_timeout=10,
        alloc_timeout=30,
        group_name='rundeck',
    ):
        self.name = name
        self.task_name = task_name
        self.group_name = group_name

        taskspec['Name'] = task_name
        taskspec['Datacenters'] = dc
        taskspec['Driver'] = driver
        taskspec['Env'] = env
        taskspec['User'] = user
        taskspec['Config'] = config
        taskspec['Artifacts'] = artifacts
        taskspec['Resources']['CPU'] = cpu
        taskspec['Resources']['MemoryMB'] = ram
        taskspec['Templates'] = [
            dict(templatespec, **t) for t in templates
        ]

        groupspec['Name'] = group_name
        groupspec['EphemeralDisk']['SizeMB'] = disk
        groupspec['Tasks'].append(taskspec)

        jobspec['Job']['Name'] = jobspec['Job']['ID'] = name
        jobspec['Job']['Priority'] = priority
        jobspec['Job']['Constraints'] = [
            dict(zip(('LTarget', 'Operand', 'RTarget'),
                     self.__variafy(i.split()))) for i in constraints]
        jobspec['Job']['TaskGroups'].append(groupspec)

        try:
            self.log.info('Starting Nomad job')
            self.log.debug(json.dumps(jobspec))
            job = self.nomad.jobs.register_job(jobspec)
        except nomad.api.exceptions.BadRequestNomadException as err:
            self.log.error(err.nomad_resp.reason)
            self.log.error(err.nomad_resp.text)
        if job['Warnings']:
            self.log.warn(job['Warnings'])

        try:
            eval = self.__evaluate(job['EvalID'])
            self.log.debug(eval)
            alloc = self.__filter_alloc(eval)['ID']
        except NomadEvaluationException:
            self.log.error('Evaluation failed')
            raise NomadEvaluationException

        try:
            self.__monitor(alloc)
        except NomadAllocationException:
            self.log.error('Allocation failed')
            raise NomadAllocationException
