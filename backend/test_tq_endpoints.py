"""Test TQ forecast API endpoints via TestClient."""
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# Test ping
r = client.get('/api/demo/tq-forecast/ping')
print('ping:', r.status_code, r.json())

# Test model_info for all 4 models
for mk in ['load_forecast', 'load_rate', 'power_factor', 'unbalance']:
    r = client.get(f'/api/demo/tq-forecast/model_info?model_key={mk}')
    j = r.json()
    print(f'model_info({mk}): {r.status_code} name={j.get("name","?")} params={j.get("params",0)} trained={j.get("has_trained_model")}')

# Test evaluate
r = client.get('/api/demo/tq-forecast/evaluate?model_key=load_forecast')
print(f'evaluate(load_forecast): {r.status_code} keys={list(r.json().keys())}')

for mk in ['load_rate', 'power_factor', 'unbalance']:
    r = client.get(f'/api/demo/tq-forecast/evaluate?model_key={mk}')
    print(f'evaluate({mk}): {r.status_code} keys={list(r.json().keys())}')

# Test training_log
r = client.get('/api/demo/tq-forecast/training_log?model_key=load_forecast')
print(f'training_log(load_forecast): {r.status_code} keys={list(r.json().keys())}')

# Test figures
r = client.get('/api/demo/tq-forecast/figures?model_key=power_factor')
print(f'figures(power_factor): {r.status_code} count={len(r.json().get("data",[]))}')

# Test predict for all 4 models
for mk in ['load_forecast', 'load_rate', 'power_factor', 'unbalance']:
    r = client.post(f'/api/demo/tq-forecast/predict?model_key={mk}')
    j = r.json()
    print(f'predict({mk}): {r.status_code} metrics={j.get("metrics",{})}')

print()
print('All TQ API endpoints verified OK!')
