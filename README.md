# CAD-to-Robot: from a new part to a robot pick, without manual labelling

**Status: work in progress (week 1).** The synthetic data pipeline and first detector work. Real-photo testing and robot integration are next.

## The problem

Programming and commissioning are a large share of a robot system's cost, and small manufacturers often wait months for a system integrator. Every new part needs new vision training data, which usually means photographing and labelling hundreds of images by hand.

This project explores a faster path: **generate labelled training images automatically in simulation, train a detector, and hand the detections to a robot**, with every step measured.

## Pipeline

```
Part model -> Isaac Sim synthetic data (randomised) -> labels checked -> YOLO dataset -> YOLO detector
           -> (next) real-photo test -> ROS 2 perception -> pick / place skills -> digital-twin safety check -> robot
```

## Results so far

| Run | Training data | Model | Precision | Recall | mAP50 | mAP50-95 | Training time | Inference |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v1 | 500 synthetic images, 5 cm cube on a table | YOLO11n, 50 epochs, 640 px | 1.00 | 1.00 | 0.995 | 0.954 | 3.2 min | 4.5 ms / image |

Note: v1 is validated on synthetic images only. The real-photo test (sim-to-real gap) is the next experiment.

## Tools

- NVIDIA Isaac Sim 6.2 with Omniverse Replicator (synthetic data)
- Ultralytics YOLO11, PyTorch 2.11 with CUDA
- Hardware: laptop with RTX 3060 (6 GB), 16 GB RAM

## Repository structure

```
scenes/work_cell.usd          Franka arm, table and test part, built in the Isaac Sim GUI
scripts/02_generate_data.py   Builds the scene in code, randomises part pose and lighting, writes images + boxes
scripts/03_check_labels.py    Draws the saved boxes onto images to verify labels visually
scripts/04_to_yolo.py         Converts Isaac Sim output to a YOLO dataset (90/10 train/val split)
runs/v1/                      Training results and the trained model (best.pt)
```

## How to run

```bat
:: 1. Generate synthetic data (Isaac Sim's Python)
C:\isaacsim\python.bat scripts\02_generate_data.py
C:\isaacsim\python.bat scripts\03_check_labels.py

:: 2. Convert and train (separate Python environment)
python -m venv .venv
.venv\Scripts\activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
pip install ultralytics
python scripts\04_to_yolo.py
yolo detect train data=data\yolo_v1\data.yaml model=yolo11n.pt epochs=50 imgsz=640 batch=16 workers=2 project=runs name=v1
```

## What went wrong and how I fixed it

- **Half-rendered first frames.** The first captured frames showed editor grid lines and incomplete lighting. Cause: the renderer had not converged yet. Fix: 8 render subframes per capture.
- **Missing labels in 20-40% of images.** Visual label checking showed the camera looking horizontally and the part floating or hidden inside the table. Cause: the new stage was not Z-up, so "sideways" randomisation became random height. Fix: set the stage to Z-up and metres explicitly. Result: 10 of 10 checked frames labelled correctly.

## Next steps

- [ ] Test the v1 detector on real photos of a real cube and measure the sim-to-real gap
- [ ] Add colour, texture and distractor randomisation; retrain (v2) and compare on the same photos
- [ ] Measure how many real images close the gap
- [ ] ROS 2 perception node and robot pick in simulation
- [ ] Digital-twin safety check before execution

## Author

Venkatesh Vishal Patil, M.Sc. AI & Robotics, Hochschule Hof
