import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import os
from datetime import datetime, timedelta

# =========================
# ===== USER INPUTS ======
# =========================
calibration_path = r'/scratchsan/medellin/lroserom/tesis/runs/xbeach/calibration'
csv_path         = r'/scratchsan/medellin/lroserom/tesis/data/old/processed/csv/RBR3_wave_params_from_npz.csv'
fig_path         = r'/scratchsan/medellin/lroserom/tesis/figures/model_runs/xbeach/calibration/RBR3point_compare_Hrms.png'

case_configs = {
    # 'C1': {'x_target': 2985, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C2': {'x_target': 2715, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C3': {'x_target': 2985, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C4': {'x_target': 2985, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C5': {'x_target': 2985, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C6': {'x_target': 2985, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C7': {'x_target': 2985, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C8': {'x_target': 2985, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C9': {'x_target': 2985, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C10': {'x_target': 2985, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C11': {'x_target': 2985, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C12': {'x_target': 2985, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'V1': {'x_target': 2985, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C14': {'x_target': 2985, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    'C15': {'x_target': 2985, 'dx': 5.0, 't0': datetime(2025, 5, 20, 7)}

    # 'C1': {'x_target': 1850, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C2': {'x_target': 1560, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C3': {'x_target': 1850, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C4': {'x_target': 1850, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C5': {'x_target': 1850, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C6': {'x_target': 1850, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C7': {'x_target': 1850, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C8': {'x_target': 1850, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C9': {'x_target': 1850, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C10': {'x_target': 1850, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C11': {'x_target': 1850, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C12': {'x_target': 1850, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C13': {'x_target': 1850, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'V1': {'x_target': 1850, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)},
    # 'C14': {'x_target': 1850, 'dx': 5.0, 't0': datetime(2025, 5, 11, 13)}
}
# =========================

# ---- Load observed data ----
df_obs = pd.read_csv(csv_path)
df_obs.columns = df_obs.columns.str.strip()
df_obs['datetime'] = pd.to_datetime(df_obs['date'])
obs_time = df_obs['datetime']
obs_hrms = df_obs['Hs[m]']

# ---- Find all .nc in calibration folder ----
cases = {}
for folder in os.listdir(calibration_path):
    case_path = os.path.join(calibration_path, folder)
    output_path = os.path.join(case_path, 'output')
    if os.path.isdir(output_path):
        for file in os.listdir(output_path):
            if file.endswith('.nc'):
                case_name = folder.split('_')[-1]  # MayJun2025_C1 → C1
                nc_file = os.path.join(output_path, file)
                cases[case_name] = nc_file

print("Found cases:", cases)

# ---- Read model data ----
model_data = {}
for case, nc_path in cases.items():
    if case not in case_configs:
        print(f"Skipping {case} - no config defined.")
        continue

    cfg = case_configs[case]
    ds = xr.open_dataset(nc_path)
    ix = int(round(cfg['x_target'] / cfg['dx']))
    x  = ds.globalx.values[0, :]
    H  = ds.H.values[:, 0, ix]

    time_model = np.array([
        cfg['t0'] + timedelta(seconds=float(t))
        for t in ds.globaltime.values
    ])

    model_data[case] = {
        "time": time_model,
        "H": H,
        "x": x[ix]
    }

# ---- Plot ----
plt.figure(figsize=(10,5))

# Observed
plt.plot(obs_time, obs_hrms, color='black', lw=2, label='Observed')

# Model runs
colors = plt.cm.tab10.colors
for i, (case, data) in enumerate(sorted(model_data.items())):
    plt.plot(
        data["time"],
        data["H"],
        lw=1.5,
        color=colors[i % len(colors)],
        label=f'Model {case}'
    )

# Labeling
plt.xlabel("Time")
plt.ylabel("Hrms [m]")
plt.title("Hrms comparison at shared target location")
plt.legend()
plt.grid(alpha=0.3)
#plt.xlim(xmin, xmax)      # e.g., pd.Timestamp("2025-05-11"), pd.Timestamp("2025-05-16")
plt.ylim(0, 0.25) 
plt.gcf().autofmt_xdate()
plt.tight_layout()

# Save
os.makedirs(os.path.dirname(fig_path), exist_ok=True)
plt.savefig(fig_path, dpi=300, bbox_inches="tight")
plt.close()

print(f"Figure saved at: {fig_path}")
