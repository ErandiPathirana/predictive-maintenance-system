# Frontend tests

The frontend tests are stored next to the code they test:

- `frontend/src/api/client.test.ts` — API client: success, structured errors, network failure
- `frontend/src/components/StatusLamp.test.tsx` — component rendering
- `frontend/src/pages/StatusPage.test.tsx` — loading, not-loaded, ready and error-with-retry states

Run them:
```powershell
cd frontend
npm test
```
