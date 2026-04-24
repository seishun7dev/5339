"""
Generate the 5 visualisations, some are described in the report.
Outputs are saved to data/plots/.
"""

import os
import warnings
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

warnings.filterwarnings("ignore")

ROOT = os.path.dirname(os.path.abspath(__file__))

def p(*parts):
    return os.path.join(ROOT, *parts)

os.makedirs(p("data/plots"), exist_ok=True)

# ── load data ──────────────────────────────────────────────────────────────────
gen = pd.read_csv(p("data/curated/generation.csv"))
fac = pd.read_csv(p("data/curated/facility.csv"))
abs_pop = pd.read_csv(p("data/curated/abs_population.csv"))

# drop JV double-counted rows from generation analysis
gen_clean = gen[~gen["jv_double_counted"].fillna(False)]

# ── colour palette – broad fuel groups ────────────────────────────────────────
FUEL_COLOURS = {
    "Solar":              "#f5c518",
    "Wind":               "#4db6d4",
    "Hydro":              "#2196f3",
    "Black Coal":         "#424242",
    "Brown Coal":         "#8d6e63",
    "Gas":                "#ff9800",
    "Gas/Diesel":         "#ffc107",
    "Landfill Gas":       "#8bc34a",
    "Biogas":             "#558b2f",
    "Coal Seam Methane":  "#795548",
    "Waste Coal Mine Gas":"#a1887f",
    "Bagasse":            "#66bb6a",
    "Biofuel":            "#388e3c",
    "Diesel":             "#e53935",
    "Liquid Fuel":        "#ef9a9a",
    "Battery":            "#ab47bc",
    "Wind/Diesel":        "#80cbc4",
    "Wood":               "#6d4c41",
    "Kerosene":           "#ff7043",
    "Macadamia Nut Shells":"#aed581",
    "Multiple sources":   "#bdbdbd",
    "Sludge Biogas":      "#9ccc65",
}

def fuel_colour(fuel):
    return FUEL_COLOURS.get(fuel, "#9e9e9e")

STYLE = dict(figure_facecolor="white", axes_facecolor="#f9f9f9")

# ══════════════════════════════════════════════════════════════════════════════
# Plot 1 – NGER facility count per year, segmented by primary fuel
# ══════════════════════════════════════════════════════════════════════════════
print("Plot 1: facility count by year and fuel …")

# one row per facility-year (F rows only, dedup by facility_id+year)
fac_year = (
    gen_clean[gen_clean["row_type"] == "F"]
    .drop_duplicates(subset=["facility_id", "financial_year_end"])
    [["financial_year_end", "primary_fuel"]]
)

pivot1 = (
    fac_year.groupby(["financial_year_end", "primary_fuel"])
    .size()
    .unstack(fill_value=0)
    .sort_index()
)

# order columns: renewables first, then fossil
col_order = [c for c in ["Solar", "Wind", "Hydro"] if c in pivot1.columns]
fossil     = [c for c in pivot1.columns if c not in col_order]
col_order += sorted(fossil)
pivot1 = pivot1[col_order]

fig, ax = plt.subplots(figsize=(11, 5))
fig.patch.set_facecolor("white")
ax.set_facecolor("#f9f9f9")

bottom = np.zeros(len(pivot1))
for fuel in col_order:
    vals = pivot1[fuel].values
    ax.bar(pivot1.index, vals, bottom=bottom,
           color=fuel_colour(fuel), label=fuel, edgecolor="white", linewidth=0.4)
    bottom += vals

ax.set_title("NGER-Reporting Facilities by Year and Primary Fuel", fontsize=13, fontweight="bold", pad=10)
ax.set_xlabel("Financial Year End")
ax.set_ylabel("Number of Facilities")
ax.set_xticks(pivot1.index)
ax.set_xticklabels([f"FY{y-1}/{str(y)[-2:]}" for y in pivot1.index], rotation=30, ha="right")
ax.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8, frameon=True)
ax.grid(axis="y", linestyle="--", alpha=0.5)
ax.spines[["top","right"]].set_visible(False)

plt.tight_layout()
plt.savefig(p("data/plots/plot1_facility_count_by_fuel.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  saved.")

# ══════════════════════════════════════════════════════════════════════════════
# Plot 2 – Stacked bar: total Scope 1 emissions by fuel per year
# ══════════════════════════════════════════════════════════════════════════════
print("Plot 2: Scope 1 emissions by fuel and year …")

em = (
    gen_clean[gen_clean["row_type"] == "F"]
    .groupby(["financial_year_end", "primary_fuel"])["scope1_emissions_tco2e"]
    .sum()
    .unstack(fill_value=0)
    .sort_index()
)

# keep only fuels with any meaningful emissions (>1 000 tCO2e total)
significant = em.columns[em.sum() > 1_000]
em = em[significant]

# order: high-emission fuels first
col_order2 = em.sum().sort_values(ascending=False).index.tolist()
em = em[col_order2]

fig, ax = plt.subplots(figsize=(11, 5))
fig.patch.set_facecolor("white")
ax.set_facecolor("#f9f9f9")

bottom = np.zeros(len(em))
for fuel in col_order2:
    vals = em[fuel].values / 1e6   # convert to Mt CO₂e
    ax.bar(em.index, vals, bottom=bottom,
           color=fuel_colour(fuel), label=fuel, edgecolor="white", linewidth=0.4)
    bottom += vals

ax.set_title("Total Scope 1 Emissions by Primary Fuel (NGER, F-rows)", fontsize=13, fontweight="bold", pad=10)
ax.set_xlabel("Financial Year End")
ax.set_ylabel("Scope 1 Emissions (Mt CO₂e)")
ax.set_xticks(em.index)
ax.set_xticklabels([f"FY{y-1}/{str(y)[-2:]}" for y in em.index], rotation=30, ha="right")
ax.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8, frameon=True)
ax.grid(axis="y", linestyle="--", alpha=0.5)
ax.spines[["top","right"]].set_visible(False)

plt.tight_layout()
plt.savefig(p("data/plots/plot2_scope1_by_fuel.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  saved.")

# ══════════════════════════════════════════════════════════════════════════════
# Plot 3 – Bubble map: facility locations coloured by fuel type
# ══════════════════════════════════════════════════════════════════════════════
print("Plot 3: bubble map of facility locations …")

import geopandas as gpd
from shapely.geometry import Point

# load Australia states shapefile bundled with geopandas / naturalearth
import geodatasets
land = gpd.read_file(geodatasets.get_path("naturalearth.land"))
# crop to Australia bounding box
aus = land.cx[112:155, -44:-10]

# facilities with coordinates
fac_geo = fac[fac["lat"].notna() & fac["lon"].notna()].copy()
fac_geo["geometry"] = [Point(lon, lat) for lon, lat in zip(fac_geo["lon"], fac_geo["lat"])]
gdf = gpd.GeoDataFrame(fac_geo, crs="EPSG:4326")

# broad fuel group for colouring
def broad_fuel(fuel):
    if pd.isna(fuel): return "Other"
    if "Solar" in str(fuel): return "Solar"
    if "Wind" in str(fuel): return "Wind"
    if "Hydro" in str(fuel): return "Hydro"
    if "Gas" in str(fuel) or "gas" in str(fuel): return "Gas/Biogas"
    return "Other"

gdf["fuel_group"] = gdf["fuel_source"].map(broad_fuel)

GROUP_COLOURS = {
    "Solar":     "#f5c518",
    "Wind":      "#4db6d4",
    "Hydro":     "#2196f3",
    "Gas/Biogas":"#ff9800",
    "Other":     "#bdbdbd",
}

fig, ax = plt.subplots(figsize=(12, 9))
fig.patch.set_facecolor("white")
ax.set_facecolor("#d0e8f5")

aus.plot(ax=ax, color="#e8e0d0", edgecolor="#888", linewidth=0.8)

for group, colour in GROUP_COLOURS.items():
    sub = gdf[gdf["fuel_group"] == group]
    if sub.empty:
        continue
    # size ~ installed capacity; cap outliers
    sizes = sub["installed_capacity_mw"].fillna(5).clip(upper=800) / 8 + 4
    sub.plot(ax=ax, color=colour, markersize=sizes,
             alpha=0.65, label=f"{group} (n={len(sub)})", legend=False)

ax.set_xlim(112, 155)
ax.set_ylim(-44, -10)
ax.set_title("Accredited Power Station Locations by Fuel Type\n(bubble size ∝ installed capacity MW)",
             fontsize=13, fontweight="bold", pad=10)
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")

# manual legend
from matplotlib.lines import Line2D
handles = [Line2D([0],[0], marker="o", color="w", markerfacecolor=c,
                   markersize=9, label=g)
           for g, c in GROUP_COLOURS.items()]
ax.legend(handles=handles, title="Fuel type", loc="lower left", fontsize=9, frameon=True)
ax.grid(linestyle="--", alpha=0.3)
ax.spines[["top","right"]].set_visible(False)

plt.tight_layout()
plt.savefig(p("data/plots/plot3_facility_map.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  saved.")

# ══════════════════════════════════════════════════════════════════════════════
# Plot 4 – Per-capita Scope 1 emissions by state (FY2024)
# ══════════════════════════════════════════════════════════════════════════════
print("Plot 4: per-capita emissions by state …")

# NGER Scope 1 by state, FY2024
s1_state = (
    gen_clean[
        (gen_clean["financial_year_end"] == 2024) &
        (gen_clean["row_type"] == "F")
    ]
    .groupby("state")["scope1_emissions_tco2e"]
    .sum()
    .reset_index()
)

# ABS ERP for states, 2024
state_pop = (
    abs_pop[
        (abs_pop["geography_level"] == "STATE") &
        (abs_pop["year"] == 2024)
    ]
    [["state", "estimated_resident_population_no"]]
    .dropna()
)

merged = s1_state.merge(state_pop, on="state", how="inner")
merged["per_capita_tco2e"] = (
    merged["scope1_emissions_tco2e"] / merged["estimated_resident_population_no"]
)
merged = merged.sort_values("per_capita_tco2e", ascending=False)

STATE_COLOURS = {
    "QLD": "#e65100", "WA": "#bf360c", "NSW": "#f57c00",
    "VIC": "#6a1a9a", "SA": "#0277bd", "NT": "#00695c",
    "ACT": "#558b2f", "TAS": "#01579b",
}
colours = [STATE_COLOURS.get(s, "#9e9e9e") for s in merged["state"]]

fig, ax = plt.subplots(figsize=(9, 5))
fig.patch.set_facecolor("white")
ax.set_facecolor("#f9f9f9")

bars = ax.barh(merged["state"], merged["per_capita_tco2e"], color=colours,
               edgecolor="white", linewidth=0.4)
for bar, val in zip(bars, merged["per_capita_tco2e"]):
    ax.text(val + 0.05, bar.get_y() + bar.get_height()/2,
            f"{val:.1f}", va="center", fontsize=9)

ax.set_title("Per-Capita Scope 1 Emissions by State — FY2023-24\n(NGER facility emissions ÷ ABS ERP)",
             fontsize=13, fontweight="bold", pad=10)
ax.set_xlabel("Scope 1 Emissions per Capita (t CO₂e / person)")
ax.set_ylabel("State")
ax.grid(axis="x", linestyle="--", alpha=0.5)
ax.spines[["top","right"]].set_visible(False)

plt.tight_layout()
plt.savefig(p("data/plots/plot4_per_capita_emissions.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  saved.")

# ══════════════════════════════════════════════════════════════════════════════
# Plot 5 – CER cumulative capacity (MW) by commissioning year + NGER facility count
# ══════════════════════════════════════════════════════════════════════════════
print("Plot 5: CER cumulative capacity + NGER facility count …")

fac["acc_year"] = pd.to_datetime(fac["accreditation_start_date"], errors="coerce").dt.year
annual_cap = (
    fac.dropna(subset=["acc_year", "installed_capacity_mw"])
    .groupby("acc_year")["installed_capacity_mw"]
    .sum()
    .sort_index()
)
annual_cap = annual_cap[(annual_cap.index >= 2000) & (annual_cap.index <= 2024)]
cumulative = annual_cap.cumsum()

nger_count = (
    gen_clean[gen_clean["row_type"] == "F"]
    .drop_duplicates(subset=["facility_id", "financial_year_end"])
    .groupby("financial_year_end")
    .size()
)

fig, ax1 = plt.subplots(figsize=(11, 5))
fig.patch.set_facecolor("white")
ax1.set_facecolor("#f9f9f9")

ax1.fill_between(cumulative.index, cumulative.values / 1000, alpha=0.25, color="#4db6d4")
ax1.plot(cumulative.index, cumulative.values / 1000, color="#4db6d4",
         linewidth=2.5, marker="o", markersize=5, label="Cumulative CER capacity (GW)")
ax1.set_xlabel("Year")
ax1.set_ylabel("Cumulative Accredited Capacity (GW)", color="#1565c0")
ax1.tick_params(axis="y", labelcolor="#1565c0")
ax1.set_xlim(2000, 2025)

ax2 = ax1.twinx()
ax2.set_facecolor("none")
ax2.bar(nger_count.index, nger_count.values, alpha=0.45, color="#ff9800",
        label="NGER F-row facility count", width=0.6)
ax2.set_ylabel("NGER Reporting Facilities", color="#e65100")
ax2.tick_params(axis="y", labelcolor="#e65100")

ax1.set_title("CER Cumulative Accredited Capacity vs NGER Annual Facility Count",
              fontsize=13, fontweight="bold", pad=10)

lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=9, frameon=True)
ax1.grid(axis="y", linestyle="--", alpha=0.4)
ax1.spines[["top","right"]].set_visible(False)
ax2.spines[["top"]].set_visible(False)

plt.tight_layout()
plt.savefig(p("data/plots/plot5_cer_capacity_vs_nger.png"), dpi=150, bbox_inches="tight")
plt.close()
print("  saved.")

print("\nAll plots saved to data/plots/")
