#!/bin/bash
uvicorn main:app --host localhost --port 8000 &
npm --prefix frontend run dev
