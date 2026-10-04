from pathlib import Path
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sensorColumns = ["tac", "temp", "motion"]
adjustmentColumns = ["non_wear", "gap_imputed", "jump_corrected"]

def prepareData(data):
    required = ["time", *sensorColumns]
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError("Missing columns: " + ", ".join(missing))
    cleaned = data.copy()
    if pd.api.types.is_numeric_dtype(cleaned["time"]):
        raise ValueError("Use date/time timestamps for biosensor cleaning, not elapsed seconds")
    cleaned["time"] = pd.to_datetime(cleaned["time"], errors="coerce", format="mixed", utc=True).dt.tz_localize(None)
    for column in sensorColumns:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    cleaned = cleaned.dropna(subset=["time"])
    cleaned = cleaned.drop_duplicates("time", keep="last")
    cleaned = cleaned.sort_values("time")
    return cleaned.reset_index(drop=True)

def loadData(filePath):
    filePath = Path(filePath)
    extension = filePath.suffix.lower()
    if extension == ".csv":
        data = pd.read_csv(filePath)
    elif extension in [".xlsx", ".xlsm"]:
        data = pd.read_excel(filePath, engine="openpyxl")
    else:
        raise ValueError("Choose a CSV, XLSX or XLSM biosensor file")
    selected = {}
    for column in data.columns:
        name = str(column).strip().lower()
        if "time" not in selected and ("timestamp" in name or "datetime" in name or name in ["time", "date_time", "date time"]):
            selected["time"] = column
        if "tac" not in selected and "tac" in name:
            selected["tac"] = column
        if "temp" not in selected and "temp" in name:
            selected["temp"] = column
        if "motion" not in selected and "motion" in name:
            selected["motion"] = column
    missing = [column for column in ["time", *sensorColumns] if column not in selected]
    if missing:
        raise ValueError(str(filePath) + " is missing: " + ", ".join(missing))
    cleaned = data.loc[:, [selected[column] for column in ["time", *sensorColumns]]].copy()
    cleaned.columns = ["time", *sensorColumns]
    return prepareData(cleaned)

def cleanNonwear(data, tempCutoff=28):
    if not math.isfinite(tempCutoff):
        raise ValueError("Temperature cutoff must be finite")
    cleaned = prepareData(data)
    cleaned["non_wear"] = cleaned["temp"] < tempCutoff
    cleaned.loc[cleaned["non_wear"], sensorColumns] = np.nan
    cleaned = cleaned.set_index("time")
    cleaned[sensorColumns] = cleaned[sensorColumns].interpolate("time").ffill().bfill()
    return cleaned.reset_index()

def imputeGaps(data, interval=None, maxRows=2000000):
    cleaned = prepareData(data)
    if type(maxRows) is not int or maxRows < 1:
        raise ValueError("maxRows must be a positive integer")
    cleaned["gap_imputed"] = False
    if len(cleaned) < 2:
        return cleaned
    if interval is None:
        intervals = cleaned["time"].diff().dropna()
        interval = intervals.mode().iloc[0]
    else:
        interval = pd.to_timedelta(interval)
    if pd.isna(interval) or interval <= pd.Timedelta(0):
        raise ValueError("Gap interval must be positive")
    span = cleaned["time"].iloc[-1] - cleaned["time"].iloc[0]
    estimatedRows = int(span / interval) + 1
    if estimatedRows > maxRows or len(cleaned) > maxRows:
        raise ValueError("Gap grid is too large; choose a longer interval or increase maxRows")
    observedTimes = pd.DatetimeIndex(cleaned["time"])
    grid = pd.date_range(observedTimes.min(), observedTimes.max(), freq=interval)
    completeTimes = grid.union(observedTimes).sort_values()
    if len(completeTimes) > maxRows:
        raise ValueError("Gap grid exceeds maxRows")
    cleaned = cleaned.set_index("time").reindex(completeTimes)
    cleaned.index.name = "time"
    cleaned["gap_imputed"] = ~cleaned.index.isin(observedTimes)
    cleaned[sensorColumns] = cleaned[sensorColumns].interpolate("time").ffill().bfill()
    for column in ["non_wear", "jump_corrected"]:
        if column in cleaned.columns:
            cleaned[column] = cleaned[column].fillna(False).astype(bool)
    return cleaned.reset_index()

def cleanSensorJumps(data, jumpMultiplier=6, maxSpikeWidth=120, minFlatWidth=4):
    if not math.isfinite(jumpMultiplier) or jumpMultiplier <= 0:
        raise ValueError("jumpMultiplier must be positive")
    if type(maxSpikeWidth) is not int or maxSpikeWidth < 1:
        raise ValueError("maxSpikeWidth must be a positive sample count")
    if type(minFlatWidth) is not int or minFlatWidth < 1:
        raise ValueError("minFlatWidth must be a positive sample count")
    cleaned = prepareData(data)
    cleaned["jump_corrected"] = False
    if len(cleaned) < 2 or not cleaned["tac"].notna().any():
        return cleaned
    minutes = cleaned["time"].diff().dt.total_seconds() / 60
    change = cleaned["tac"].diff()
    slope = change / minutes
    typicalChange = change.abs().replace(0, np.nan).median()
    typicalSlope = slope.abs().replace(0, np.nan).median()
    if pd.isna(typicalChange):
        typicalChange = 0
    if pd.isna(typicalSlope):
        typicalSlope = 0
    changeLimit = jumpMultiplier * typicalChange
    slopeLimit = jumpMultiplier * typicalSlope
    largeJump = ((change.abs() > changeLimit) | (slope.abs() > slopeLimit)).fillna(False).to_numpy()
    corrected = np.zeros(len(cleaned), dtype=bool)
    for start in np.where(largeJump)[0]:
        if corrected[start]:
            continue
        end = min(start + maxSpikeWidth, len(cleaned) - 1)
        stablePoints = 0
        for current in range(start + 1, end + 1):
            if abs(slope.iloc[current]) <= slopeLimit:
                stablePoints += 1
            else:
                stablePoints = 0
            if stablePoints == 3:
                end = current - 2
                break
        corrected[start:end + 1] = True
    flat = change.abs() <= typicalChange * 0.25
    flatGroups = (flat != flat.shift()).cumsum()
    for groupNumber, group in cleaned.groupby(flatGroups):
        indexes = group.index
        if not flat.loc[indexes].all() or len(indexes) < minFlatWidth:
            continue
        start = indexes[0]
        end = indexes[-1]
        if start == 0 or end == len(cleaned) - 1:
            continue
        enteredFlat = abs(change.iloc[start]) > changeLimit
        exitedFlat = abs(change.iloc[end + 1]) > changeLimit
        if enteredFlat or exitedFlat:
            corrected[start:end + 1] = True
    cleaned["jump_corrected"] = corrected
    cleaned.loc[corrected, "tac"] = np.nan
    missing = cleaned["tac"].isna()
    timeMinutes = (cleaned["time"] - cleaned["time"].iloc[0]).dt.total_seconds() / 60
    missingGroups = (missing != missing.shift()).cumsum()
    for groupNumber, group in cleaned[missing].groupby(missingGroups[missing]):
        start = group.index[0]
        end = group.index[-1]
        nearby = np.arange(max(0, start - 3), min(len(cleaned), end + 4))
        nearby = nearby[~missing.iloc[nearby].to_numpy()]
        if len(nearby) < 2:
            continue
        degree = min(2, len(nearby) - 1)
        x = timeMinutes.iloc[nearby].to_numpy(dtype=float)
        y = cleaned["tac"].iloc[nearby].to_numpy(dtype=float)
        center = x.mean()
        try:
            curve = np.polyfit(x - center, y, degree)
            cleaned.loc[start:end, "tac"] = np.polyval(curve, timeMinutes.iloc[start:end + 1] - center)
        except np.linalg.LinAlgError:
            continue
    cleaned = cleaned.set_index("time")
    cleaned["tac"] = cleaned["tac"].interpolate("time").ffill().bfill()
    return cleaned.reset_index()

def runQualityControls(filePaths, tempCutoff=28, interval=None, jumpMultiplier=6, maxSpikeWidth=120, minFlatWidth=4):
    results = []
    for number, filePath in enumerate(filePaths, start=1):
        name = Path(filePath).name
        original = loadData(filePath)
        cleaned = cleanNonwear(original, tempCutoff)
        cleaned = imputeGaps(cleaned, interval)
        cleaned = cleanSensorJumps(cleaned, jumpMultiplier, maxSpikeWidth, minFlatWidth)
        print("Processing", name)
        for column in adjustmentColumns:
            print(column + ":", int(cleaned[column].sum()))
        results.append({"number": number, "name": name, "original": original,
                        "final": cleaned, "temp_cutoff": tempCutoff, "source": str(Path(filePath).resolve())})
    return results

def flagPercent(data, column):
    if data.empty or column not in data.columns:
        return 0.0
    return float(data[column].fillna(False).astype(bool).mean() * 100)

def computeTacFeatures(results):
    rows = []
    for result in results:
        original = prepareData(result["original"])
        final = prepareData(result["final"])
        originalTac = original.dropna(subset=["tac"])
        finalTac = final.dropna(subset=["tac"])
        if finalTac.empty:
            rows.append({"dataset": result["name"], "error": "No valid TAC data"})
            continue
        start = finalTac.iloc[0]
        end = finalTac.iloc[-1]
        peak = finalTac.loc[finalTac["tac"].idxmax()]
        riseDuration = (peak["time"] - start["time"]).total_seconds() / 60
        fallDuration = (end["time"] - peak["time"]).total_seconds() / 60
        riseRate = (peak["tac"] - start["tac"]) / riseDuration if riseDuration > 0 else np.nan
        fallRate = (peak["tac"] - end["tac"]) / fallDuration if fallDuration > 0 else np.nan
        cutoff = result.get("temp_cutoff", 28)
        nonwearPercent = float(original["temp"].lt(cutoff).mean() * 100) if len(original) else 0
        rows.append({
            "dataset": result["name"], "start_time": start["time"],
            "peak_time": peak["time"], "end_time": end["time"],
            "peak_tac": peak["tac"], "min_tac": finalTac["tac"].min(),
            "max_tac": finalTac["tac"].max(), "rise_duration_min": riseDuration,
            "rise_rate": riseRate, "fall_duration_min": fallDuration,
            "fall_rate": fallRate, "percent_imputed": flagPercent(final, "gap_imputed"),
            "percent_non_wear": nonwearPercent,
            "percent_jump_corrected": flagPercent(final, "jump_corrected"),
            "original_noise_std": originalTac["tac"].diff().std(),
            "final_noise_std": finalTac["tac"].diff().std()
        })
    return pd.DataFrame(rows)

def plotFinalResult(result, figureFolder, show=False):
    original = result["original"]
    final = result["final"]
    figure, axis = plt.subplots(figsize=(13, 5))
    try:
        axis.plot(original["time"], original["tac"], color="gray", linewidth=1, label="Original")
        axis.plot(final["time"], final["tac"], color="blue", linewidth=1.5, label="Cleaned")
        styles = [("non_wear", "orange", "Non-wear cleaned", "o"),
                  ("gap_imputed", "red", "Gap imputed", "x"),
                  ("jump_corrected", "purple", "Jump corrected", "s")]
        for column, color, label, marker in styles:
            if column in final.columns:
                adjusted = final[column].fillna(False).astype(bool)
                if adjusted.any():
                    axis.scatter(final.loc[adjusted, "time"], final.loc[adjusted, "tac"],
                                 color=color, marker=marker, s=28, label=label, zorder=4)
        axis.set_title(result["name"])
        axis.set_xlabel("Time (UTC)")
        axis.set_ylabel("TAC (ug/L)")
        axis.grid(True)
        axis.legend()
        figure.autofmt_xdate()
        figure.tight_layout()
        folder = Path(figureFolder)
        folder.mkdir(parents=True, exist_ok=True)
        safeName = "".join(character if character.isalnum() or character in ["-", "_"] else "_"
                           for character in Path(result["name"]).stem)
        figurePath = folder / (str(result.get("number", 1)) + "_" + safeName + ".png")
        figure.savefig(figurePath, dpi=200, bbox_inches="tight")
        if show:
            plt.show()
        return figurePath
    finally:
        plt.close(figure)

def exportResults(results, outputFile, figureFolder, observations=None):
    if not results:
        raise ValueError("Choose at least one biosensor file")
    outputFile = Path(outputFile)
    if outputFile.suffix.lower() != ".xlsx":
        raise ValueError("Choose an .xlsx output file")
    for result in results:
        if result.get("source") and outputFile.resolve() == Path(result["source"]).resolve():
            raise ValueError("Choose an output file different from the original input")
    features = computeTacFeatures(results)
    adjustmentRows = []
    noteRows = []
    observations = observations or {}
    for position, result in enumerate(results):
        final = result["final"]
        flags = final.reindex(columns=adjustmentColumns).fillna(False).astype(bool)
        counts = flags.sum()
        adjustedPercent = float(flags.any(axis=1).mean() * 100) if len(final) else 0
        adjustmentRows.append({"dataset": result["name"], "final_rows": len(final),
                               "non_wear_adjusted_rows": int(counts["non_wear"]),
                               "gap_imputed_rows": int(counts["gap_imputed"]),
                               "jump_corrected_rows": int(counts["jump_corrected"]),
                               "percent_any_adjusted": adjustedPercent})
        feature = features.iloc[position]
        if pd.notna(feature.get("error")):
            insight = str(feature["error"])
        else:
            insight = (f"Peak TAC was {feature['peak_tac']:.2f} at {feature['peak_time']}. "
                       f"Rise rate was {feature['rise_rate']:.4f} TAC/min and "
                       f"fall rate was {feature['fall_rate']:.4f} TAC/min.")
        if adjustedPercent >= 20:
            quality = "High adjustment rate; review the raw and cleaned plot before interpreting."
        elif adjustedPercent >= 5:
            quality = "Moderate adjustment rate; interpretation should mention cleaning."
        else:
            quality = "Low adjustment rate; cleaned data is closer to the original signal."
        noteRows.append({"dataset": result["name"], "clinical_insight": insight,
                         "quality_recommendation": quality,
                         "adjustment_summary": f"Non-wear rows: {counts['non_wear']}; gap-imputed rows: {counts['gap_imputed']}; jump-corrected rows: {counts['jump_corrected']}.",
                         "personal observations": observations.get(result["name"], "")})
        plotFinalResult(result, figureFolder)
    adjustments = pd.DataFrame(adjustmentRows)
    notes = pd.DataFrame(noteRows)
    outputFile = Path(outputFile)
    outputFile.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(outputFile, engine="openpyxl", datetime_format="yyyy-mm-dd hh:mm:ss") as writer:
        for result in results:
            result["final"].to_excel(writer, sheet_name=f"option_{result['number']}", index=False)
        features.to_excel(writer, sheet_name="feature_computation", index=False)
        adjustments.to_excel(writer, sheet_name="adjustment_summary", index=False)
        notes.to_excel(writer, sheet_name="clinical_notes", index=False)
    return features, adjustments, notes

def runProject(filePaths, outputFile="artifacts/biosensor_cleaned.xlsx", figureFolder="artifacts/biosensor_figures", tempCutoff=28, interval=None, jumpMultiplier=6, maxSpikeWidth=120, minFlatWidth=4, observations=None):
    results = runQualityControls(filePaths, tempCutoff, interval, jumpMultiplier, maxSpikeWidth, minFlatWidth)
    features, adjustments, notes = exportResults(results, outputFile, figureFolder, observations)
    print(features.to_string(index=False))
    print("Saved", Path(outputFile).resolve())
    return results, features, adjustments, notes

load_data = loadData
clean_nonwear = cleanNonwear
impute_gaps = imputeGaps
clean_sensor_jumps = cleanSensorJumps
run_quality_controls = runQualityControls
compute_tac_features = computeTacFeatures
plot_final_result = plotFinalResult
export_results = exportResults
run_project = runProject
