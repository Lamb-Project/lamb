from fastapi import FastAPI
from fastapi.testclient import TestClient
from lamb.document_static import DocumentAwareStaticFiles


def test_every_hidden_component_is_private_including_future_store_names(tmp_path):
    hidden = ['.course-cache/7.json','public/7/.anything/cache.json',
              '.Learning-Scenarios/7.json','ordinary/.private.json']
    for path in hidden + ['ordinary/visible.txt']:
        file=tmp_path/path;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('fixture')
    app=FastAPI();app.mount('/static',DocumentAwareStaticFiles(directory=tmp_path))
    client=TestClient(app)
    for path in hidden:
        for encoded in (path,path.replace('.', '%2e')):
            for method in (client.get,client.head):
                assert method('/static/'+encoded).status_code == 404
    assert client.get('/static/ordinary/visible.txt').text == 'fixture'
