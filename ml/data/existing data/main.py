import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.stats import spearmanr

base = '/home/sinwin/gps-spoofing-and-ai-detection/ml/data/existing data/'

# ── Load files ──────────────────────────────────────────────
df_3d = pd.read_excel(base + 'GPS_Dataset_3D_8_Channels_Authentic_and_Simulated.xlsx', header=[0, 1])
df_2d = pd.read_excel(base + 'GPS_Data_Simplified_2D_Feature_Map.xlsx', header=0)
df_raw = pd.read_excel(base + 'GPS_Raw_Data_Authentic_Data_3D_8_Channels.xlsx', header=[0, 1])

print("Files loaded.")

# ── Helper ───────────────────────────────────────────────────
FEATURES = ['PRN', 'Carrier_Doppler_hz', 'Pseudorange_m', 'RX_time',
            'TOW_at_current_symbol_s', 'Carrier_phase_cycles',
            'EC', 'LC', 'PC', 'PIP', 'PQP', 'TCD', 'CN0']
CHANNELS = ['ch0', 'ch1', 'ch2', 'ch3', 'ch4', 'ch5', 'ch6', 'ch7']
CLASS_COLORS = {0: '#2ecc71', 1: '#e74c3c', 2: '#e67e22', 3: '#9b59b6'}
CLASS_LABELS = {0: 'Legitimate', 1: 'Spoofed Type 1', 2: 'Spoofed Type 2', 3: 'Spoofed Type 3'}

# ════════════════════════════════════════════════════════════
# 1. CLASS DISTRIBUTION
# ════════════════════════════════════════════════════════════
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.suptitle('Class Distribution', fontsize=14, fontweight='bold')

# 2D file
counts_2d = df_2d['Output'].value_counts().sort_index()
axes[0].bar([CLASS_LABELS[i] for i in counts_2d.index],
            counts_2d.values,
            color=[CLASS_COLORS[i] for i in counts_2d.index])
axes[0].set_title('2D Feature Map (510k rows)')
axes[0].set_ylabel('Sample count')
for i, v in enumerate(counts_2d.values):
    axes[0].text(i, v + 2000, f'{v:,}\n({100*v/len(df_2d):.1f}%)', ha='center', fontsize=9)

# 3D file — ch0
counts_3d = df_3d['Output']['ch0'].value_counts().sort_index()
axes[1].bar([CLASS_LABELS[i] for i in counts_3d.index],
            counts_3d.values,
            color=[CLASS_COLORS[i] for i in counts_3d.index])
axes[1].set_title('3D 8-Channel (158k rows, ch0)')
axes[1].set_ylabel('Sample count')
for i, v in enumerate(counts_3d.values):
    axes[1].text(i, v + 500, f'{v:,}\n({100*v/len(df_3d):.1f}%)', ha='center', fontsize=9)

plt.tight_layout()
plt.savefig('01_class_distribution.png', dpi=150)
plt.close()
print("Saved: 01_class_distribution.png")

# ════════════════════════════════════════════════════════════
# 2. FEATURE CORRELATIONS WITH OUTPUT (Spearman) — 2D file
# ════════════════════════════════════════════════════════════
features_2d = ['PRN', 'DO', 'PD', 'RX', 'TOW', 'CP', 'EC', 'LC', 'PC', 'PIP', 'PQP', 'TCD', 'CN0']

correlations = {}
for feat in features_2d:
    corr, _ = spearmanr(df_2d[feat].fillna(0), df_2d['Output'])
    correlations[feat] = corr

corr_series = pd.Series(correlations).sort_values(key=abs, ascending=False)

fig, ax = plt.subplots(figsize=(10, 5))
colors = ['#e74c3c' if v > 0 else '#3498db' for v in corr_series.values]
bars = ax.barh(corr_series.index, corr_series.values, color=colors)
ax.axvline(0, color='black', linewidth=0.8)
ax.axvline(0.2, color='gray', linewidth=0.8, linestyle='--', label='±0.2 threshold')
ax.axvline(-0.2, color='gray', linewidth=0.8, linestyle='--')
ax.set_xlabel('Spearman Correlation with Output')
ax.set_title('Feature Correlation with Spoofing Label (2D file)', fontweight='bold')
ax.legend()
for bar, val in zip(bars, corr_series.values):
    ax.text(val + 0.005 if val >= 0 else val - 0.005,
            bar.get_y() + bar.get_height()/2,
            f'{val:.3f}', va='center', ha='left' if val >= 0 else 'right', fontsize=8)
plt.tight_layout()
plt.savefig('02_feature_correlations.png', dpi=150)
plt.close()
print("Saved: 02_feature_correlations.png")

# ════════════════════════════════════════════════════════════
# 3. FEATURE DISTRIBUTIONS PER CLASS — 2D file
# ════════════════════════════════════════════════════════════
top_features = corr_series.head(6).index.tolist()

fig, axes = plt.subplots(2, 3, figsize=(16, 8))
fig.suptitle('Feature Distributions by Class (top 6 correlated)', fontsize=13, fontweight='bold')

for ax, feat in zip(axes.flatten(), top_features):
    for cls in sorted(df_2d['Output'].unique()):
        subset = df_2d[df_2d['Output'] == cls][feat]
        subset.plot.kde(ax=ax, label=CLASS_LABELS[cls],
                        color=CLASS_COLORS[cls], linewidth=1.5)
    ax.set_title(feat)
    ax.set_xlabel('')
    ax.legend(fontsize=7)

plt.tight_layout()
plt.savefig('03_feature_distributions.png', dpi=150)
plt.close()
print("Saved: 03_feature_distributions.png")

# ════════════════════════════════════════════════════════════
# 4. TEMPORAL / BURST PATTERNS — 2D file
# ════════════════════════════════════════════════════════════
fig, axes = plt.subplots(2, 1, figsize=(16, 8))
fig.suptitle('Temporal Patterns', fontsize=13, fontweight='bold')

# Raw label over time
axes[0].scatter(range(len(df_2d)), df_2d['Output'],
                c=[CLASS_COLORS[v] for v in df_2d['Output']],
                s=0.3, alpha=0.5)
axes[0].set_ylabel('Class')
axes[0].set_title('Output label over time (each point = one sample)')
axes[0].set_yticks([0, 1, 2, 3])
axes[0].set_yticklabels([CLASS_LABELS[i] for i in range(4)])

# Rolling window — spoofing rate
window = 500
rolling_spoof = (df_2d['Output'] > 0).rolling(window).mean()
axes[1].plot(rolling_spoof, color='#e74c3c', linewidth=0.8)
axes[1].set_ylabel(f'Spoofing rate (rolling {window} samples)')
axes[1].set_xlabel('Sample index')
axes[1].set_title('Spoofing burst detection')
axes[1].axhline(0.5, color='gray', linestyle='--', linewidth=0.8)

plt.tight_layout()
plt.savefig('04_temporal_patterns.png', dpi=150)
plt.close()
print("Saved: 04_temporal_patterns.png")

# ════════════════════════════════════════════════════════════
# 5. CHANNEL COMPARISON — 3D file
# ════════════════════════════════════════════════════════════
channel_counts = {}
for ch in CHANNELS:
    if ('Output', ch) in df_3d.columns:
        counts = df_3d['Output'][ch].value_counts().sort_index()
        channel_counts[ch] = counts

fig, axes = plt.subplots(2, 4, figsize=(16, 8))
fig.suptitle('Class Distribution per Channel (3D file)', fontsize=13, fontweight='bold')

for ax, (ch, counts) in zip(axes.flatten(), channel_counts.items()):
    ax.bar([str(i) for i in counts.index],
           counts.values,
           color=[CLASS_COLORS[i] for i in counts.index])
    ax.set_title(ch)
    ax.set_xlabel('Class')
    ax.set_ylabel('Count')
    spoof_pct = 100 * (1 - counts.get(0, 0) / counts.sum())
    ax.set_title(f'{ch}  ({spoof_pct:.1f}% spoofed)')

plt.tight_layout()
plt.savefig('05_channel_comparison.png', dpi=150)
plt.close()
print("Saved: 05_channel_comparison.png")

# ════════════════════════════════════════════════════════════
# 6. CROSS-CHANNEL SPOOFING HEATMAP — 3D file
# ════════════════════════════════════════════════════════════
channel_labels = pd.DataFrame({
    ch: df_3d['Output'][ch] for ch in CHANNELS if ('Output', ch) in df_3d.columns
})

# Co-occurrence: how often are two channels spoofed simultaneously
co_occurrence = pd.DataFrame(index=CHANNELS, columns=CHANNELS, dtype=float)
for ch1 in CHANNELS:
    for ch2 in CHANNELS:
        both_spoofed = ((channel_labels[ch1] > 0) & (channel_labels[ch2] > 0)).sum()
        co_occurrence.loc[ch1, ch2] = both_spoofed

fig, ax = plt.subplots(figsize=(8, 6))
im = ax.imshow(co_occurrence.values.astype(float), cmap='Reds')
ax.set_xticks(range(8))
ax.set_yticks(range(8))
ax.set_xticklabels(CHANNELS)
ax.set_yticklabels(CHANNELS)
ax.set_title('Cross-channel spoofing co-occurrence\n(how often two channels are spoofed simultaneously)',
             fontweight='bold')
plt.colorbar(im, ax=ax, label='Co-occurrence count')
for i in range(8):
    for j in range(8):
        ax.text(j, i, f'{int(co_occurrence.values[i,j]):,}',
                ha='center', va='center', fontsize=7,
                color='white' if co_occurrence.values[i,j].astype(float) > 5000 else 'black')
plt.tight_layout()
plt.savefig('06_channel_cooccurrence.png', dpi=150)
plt.close()
print("Saved: 06_channel_cooccurrence.png")

print("\nAll plots saved. EDA complete.")