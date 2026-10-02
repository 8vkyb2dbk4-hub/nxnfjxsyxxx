"""Live RLS check with two dedicated test users; never use service_role.
Set SUPABASE_URL, SUPABASE_ANON_KEY, TEST_A_TOKEN, TEST_B_TOKEN,
TEST_A_ID, TEST_B_ID. Test B must already have a synced row.
"""
import os, requests
names=['SUPABASE_URL','SUPABASE_ANON_KEY','TEST_A_TOKEN','TEST_B_TOKEN','TEST_A_ID','TEST_B_ID']
if not all(os.getenv(k) for k in names):
    raise SystemExit('SKIPPED: live Supabase project and two test-user sessions required')
url,key,ta,tb,ida,idb=[os.environ[k] for k in names]
url=url.rstrip('/')+'/rest/v1/ai_brief_sync_state'
def headers(token=None):
    h={'apikey':key,'Content-Type':'application/json','Prefer':'return=representation'}
    if token:h['Authorization']='Bearer '+token
    return h
own=requests.get(url,params={'user_id':'eq.'+idb},headers=headers(tb),timeout=15)
own.raise_for_status();assert own.json(),'Test B must sync once before RLS verification'
state=own.json()[0]['state']
for token in [None,ta]:
    r=requests.get(url,params={'user_id':'eq.'+idb},headers=headers(token),timeout=15)
    assert r.status_code in (401,403) or (r.ok and r.json()==[]),'Cross-user read exposed state'
r=requests.patch(url,params={'user_id':'eq.'+idb},headers=headers(ta),json={'state':state},timeout=15)
assert r.status_code in (401,403) or (r.ok and r.json()==[]),'Cross-user update permitted'
r=requests.post(url,headers=headers(ta),json={'user_id':idb,'state':state},timeout=15)
assert r.status_code in (401,403),'Cross-user insert not rejected'
print('Live RLS passed: anonymous/cross-user read, cross-user update and insert blocked')
