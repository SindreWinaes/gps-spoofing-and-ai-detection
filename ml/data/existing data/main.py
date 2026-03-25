import pandas as pd

base = '/home/sinwin/gps-spoofing-and-ai-detection/ml/data/existing data/'

# ── Load files ──────────────────────────────────────────────
print("Loading files...")
df_2d = pd.read_excel(base + 'GPS_Data_Simplified_2D_Feature_Map.xlsx', header=0)
df_3d = pd.read_excel(base + 'GPS_Dataset_3D_8_Channels_Authentic_and_Simulated.xlsx', header=[0, 1])
df_raw = pd.read_excel(base + 'GPS_Raw_Data_Authentic_Data_3D_8_Channels.xlsx', header=[0, 1])
print("Done.\n")

# ── 2D Dataset ───────────────────────────────────────────────
print("=" * 50)
print("DATASET 1: GPS_Data_Simplified_2D_Feature_Map")
print("=" * 50)
print("Rows:     {:,}".format(len(df_2d)))
print("Columns:  {}".format(len(df_2d.columns)))
print("Features: {}".format(df_2d.columns.tolist()))
print("Missing:  {}".format(df_2d.isnull().sum().sum()))
print("\nClass distribution:")
counts = df_2d['Output'].value_counts().sort_index()
for cls, count in counts.items():
    print("  Class {}: {:>7,}  ({:.1f}%)".format(cls, count, 100*count/len(df_2d)))

# ── 3D Labeled Dataset ───────────────────────────────────────
print("\n" + "=" * 50)
print("DATASET 2: GPS_Dataset_3D_8_Channels_Authentic_and_Simulated")
print("=" * 50)
print("Rows:     {:,}".format(len(df_3d)))
print("Columns:  {} ({} features x 8 channels)".format(len(df_3d.columns), len(df_3d.columns.get_level_values(0).unique())))
print("Features: {}".format(df_3d.columns.get_level_values(0).unique().tolist()))
print("Missing:  {}".format(df_3d.isnull().sum().sum()))
print("\nClass distribution (ch0):")
counts = df_3d['Output']['ch0'].value_counts().sort_index()
for cls, count in counts.items():
    print("  Class {}: {:>7,}  ({:.1f}%)".format(cls, count, 100*count/len(df_3d)))

# ── 3D Raw Dataset ───────────────────────────────────────────
print("\n" + "=" * 50)
print("DATASET 3: GPS_Raw_Data_Authentic_Data_3D_8_Channels")
print("=" * 50)
print("Rows:     {:,}".format(len(df_raw)))
print("Columns:  {} ({} features x 8 channels)".format(len(df_raw.columns), len(df_raw.columns.get_level_values(0).unique())))
print("Features: {}".format(df_raw.columns.get_level_values(0).unique().tolist()))
print("Missing:  {}".format(df_raw.isnull().sum().sum()))
print("Labels:   None (authentic data only)")