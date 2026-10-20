import json
import pytest
from repopilot.model_agents import ChatCompletionExecutor, ModelAgentError


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self, n):
        return self.payload[:n]


def test_model_executor_parses_grounded_proposal(monkeypatch):
    def fake_open(req, timeout):
        assert req.get_header('Authorization') == 'Bearer secret'
        assert req.full_url.endswith('/chat/completions')
        return FakeResponse({'choices': [{'message': {'content': json.dumps({
            'proposal': 'Update timeout handling', 'actions': ['Add regression test'], 'citations': ['sandbox.py:1-10']})}}]})
    monkeypatch.setattr('repopilot.model_agents.urlrequest.urlopen', fake_open)
    executor = ChatCompletionExecutor(model='test-model', api_key='secret')
    out = executor('testing', 'fix timeouts', [{'citation': 'sandbox.py:1-10', 'text': 'timeout'}], {})
    assert out['role'] == 'testing'
    assert out['citations'] == ['sandbox.py:1-10']


def test_model_executor_rejects_fake_citations(monkeypatch):
    monkeypatch.setattr('repopilot.model_agents.urlrequest.urlopen', lambda *a, **k: FakeResponse({
        'choices': [{'message': {'content': json.dumps({
            'proposal': 'Fine', 'actions': [], 'citations': ['invented.py:1']})}}]}))
    with pytest.raises(ModelAgentError, match='cited'):
        ChatCompletionExecutor(model='test', api_key='secret')('review', 'task', [], {})


def test_model_executor_rejects_http_base_url():
    with pytest.raises(ValueError, match='HTTPS'):
        ChatCompletionExecutor(model='test', api_key='secret', base_url='http://example.com')


def test_model_executor_requires_credentials(monkeypatch):
    monkeypatch.delenv('REPOPILOT_API_KEY', raising=False)
    monkeypatch.delenv('REPOPILOT_MODEL', raising=False)
    with pytest.raises(ValueError, match='required'):
        ChatCompletionExecutor.from_environment()


def test_model_executor_rejects_bad_response(monkeypatch):
    monkeypatch.setattr('repopilot.model_agents.urlrequest.urlopen', lambda *a, **k: FakeResponse({'choices': []}))
    with pytest.raises(ModelAgentError, match='JSON proposal'):
        ChatCompletionExecutor(model='test', api_key='secret')('testing', 'task', [], {})
