# Ride Pooling System (Sweep-Line + H3 + OSRM)

## Overview

This project implements a **scalable, low-memory, ride pooling system** that matches incoming ride requests with active rides using:

- Sweep-line streaming algorithm
- H3 spatial indexing
- Direction-aware trajectory similarity
- OSRM-based detour validation

The system processes large datasets efficiently and outputs valid ride pairs for pooling.

---

## Core Approach

The algorithm avoids brute-force matching by:

1. Maintaining **active rides in a min-heap (by trip end time)**
2. Using **H3 indexing** to restrict candidate search
3. Applying **multi-stage filtering**:
   - Spatial proximity (H3 neighbors)
   - Direction compatibility (bearing)
   - Trajectory similarity (hex overlap)
   - Detour validation (OSRM)

---

## Pipeline Flow

```
Parquet Files → Streaming Processing
             → Active Ride Buffer (Heap)
             → H3 Neighbor Lookup
             → Similarity Filtering
             → OSRM Detour Check
             → Valid Matches → pooled28.parquet
```

---

## Input Requirements

### 1. Ride Data

Directory:
```
./poolingdata2/
```

Each parquet must contain:

| Column | Description |
|--------|------------|
| `rid` | Ride ID |
| `ts` | Timestamp |
| `lat`, `lon` | Coordinates |
| `rideStatus` | `ON_PICKUP` / `ON_RIDE` |

---

### 2. Precomputed Metadata

File:
```
./data/ride_meta_sim_combined.pkl
```

Each ride must include:

- `journey_hexes`
- `trip_end_time`
- `trip_end_lat`
- `trip_end_lon`

---

### 3. OSRM Server (Required)

Run locally:

```bash
docker run -t -i -p 5000:5000 osrm/osrm-backend osrm-routed
```

---

## Output Schema

| Column | Description |
|--------|------------|
| `batchid` | Unique batch ID |
| `ts` | Match timestamp |
| `rid` | New ride request |
| `matched_rid` | Assigned Active ride |
| `rid_hexB` | Pickup hex |
| `rid_hexA` | Active ride hex |
| `matched_sim_score` | Route overlap score |
| `directA`, `directB` | Direct distances |
| `detourA`, `detourB` | Detour % |
| `path` | Route type (ABAB / ABBA) |
| `pathdis` | Total pooled route distance |
| `pickup_dis` | Pickup leg distance |
| `destins_dis` | Final drop distance |

---

## Data link

https://drive.google.com/drive/u/6/folders/1b1CHugAN0ENuiOoMrL5zzT4O87Fzn37y

---

# VKT (Vehicle Kilometers Travelled) Analysis

## Goal

Measure efficiency of pooling by comparing:

- Distance without pooling
- Distance with pooling

---

## Definitions

- **Original VKT** = directA + directB  
- **Pooled VKT** = pathdis  
- **Savings** = Original − Pooled  

---

## Implementation

```python
import pandas as pd

df = pd.read_parquet("pooled28.parquet")

df["original_vkt"] = df["directA"] + df["directB"]
df["pooled_vkt"] = df["pathdis"]

df["vkt_savings"] = df["original_vkt"] - df["pooled_vkt"]

total_original = df["original_vkt"].sum()
total_pooled = df["pooled_vkt"].sum()

savings_pct = (total_original - total_pooled) / total_original * 100

print(f"VKT Reduction: {savings_pct:.2f}%")
```

---

## Interpretation

| Metric | Meaning |
|--------|--------|
| VKT Reduction ↑ | Better efficiency |
| VKT Savings ↑ | Cost + fuel savings |
| Negative savings | Bad matches |

---

# Data Insights & Analysis

## 1. Pooling Efficiency

```python
df["matched_sim_score"].describe()
```

Higher score → better trajectory overlap

---

## 2. Detour Analysis

```python
df[["detourA", "detourB"]].describe()
```

Keep detour ≤ 30% for good UX

---

## 3. Match Throughput

```python
len(df)
```

 Total successful pooled rides

---

## 4. VKT Savings Distribution

```python
df["vkt_savings"].describe()
```

 Detect consistency + bad matches

---

## 5. Route Type Analysis

```python
df["path"].value_counts()
```

 Understand ABAB vs ABBA patterns

---

## Visualization

```python
import matplotlib.pyplot as plt

plt.figure()
plt.bar(["Original", "Pooled"], [total_original, total_pooled])
plt.title("VKT Reduction")
plt.show()

plt.figure()
plt.hist(df["detourA"], bins=50)
plt.title("Detour Distribution")
plt.show()

plt.figure()
plt.hist(df["matched_sim_score"], bins=50)
plt.title("Similarity Score")
plt.show()
```

---

# Key Pitch Points

- Real-time ride pooling system  
- Reduces total travel distance (VKT)  
- Uses trajectory similarity (not naive proximity)  
- Ensures low detour for passengers  
- Scalable + memory-efficient  

---

# System Strengths

- O(N log N) via sweep-line + heap  
- No full dataset loading  
- Fast H3-based filtering  
- Accurate OSRM routing  

---

# Limitations

- OSRM latency bottleneck  
- Only 2-rider pooling  
- Static thresholds  

---

# Future Work

- Multi-rider pooling (3+)  
- ML-based matching  
- OSRM caching  
- Kafka + Spark pipeline  

---

# Conclusion

A scalable, efficient ride pooling system achieving:

- Reduced VKT  
- Better route matching  
- Low passenger detour  