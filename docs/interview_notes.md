# Interview Notes

## How to explain the project

I built EdgeSense-MA to demonstrate multi-agent AI at the edge. The system runs on Raspberry Pi 5 and combines camera-based object detection, environmental sensor monitoring, audio-event detection, and a reasoning layer. Each modality is handled by a separate FastAPI microservice. The final decision is exposed through a REST API and dashboard. The project is designed to support ONNX optimization and benchmarking.

## Questions to prepare for

- Why microservices instead of one script?
- How do you measure latency?
- What changes after ONNX optimization?
- How does the DecisionAgent combine modalities?
- How would this change on Jetson Orin Nano?
