# RazorPay 3.0 Live — Fixed Frontend

This frontend is wired to the FastAPI backend on port 8003.

## Important
- Bike searches go through the backend to **live BikeWale retrieval**.
- Car searches go through the backend to **live CarDekho retrieval**.
- The frontend does not use the local vehicle JSON as a source for bike/car results.
- Recent searches are stored in the browser and shown under "Recent searches".
- Text input works with both the Send button and Enter.
- Voice input uses Chrome Speech Recognition when available.

## Run

Terminal 1 — backend:

```powershell
cd "D:\Razorpay 3.0\Razorpay_3.0_Live"
python -m uvicorn backend.server:app --reload --host 127.0.0.1 --port 8003
```

Terminal 2 — frontend:

```powershell
cd "D:\Razorpay 3.0\Razorpay_3.0_Live"
python -m http.server 8000 --bind 127.0.0.1
```

Open:

`http://127.0.0.1:8000`

First verify:

`http://127.0.0.1:8003/api/health`

It should report `status: ok` and show BikeWale and CarDekho as the vehicle sources.

## Replace files

Copy these three files into your existing `Razorpay_3.0_Live` folder:

- index.html
- app.js
- styles.css

The backend folder does not need to be replaced.
