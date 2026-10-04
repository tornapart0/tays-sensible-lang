# Summer biosensor cleaning

This module brings the nine functions from your summer TAC notebooks into
MyLang. The reference was `final_version_of_TA_finalig.ipynb`, compared with
`TA_final_ig_one_function_per_cell_rewritten.ipynb` in your Downloads folder.
It keeps the temperature masking, time interpolation, jump/slope thresholds,
flat-artifact correction, local quadratic repair, feature calculations, marked
plots and Excel summary sheets from that work.

The public function names and examples follow the camelCase naming and separate
brace lines in your APCSA `Calculator.java`, `Main.java` and
`scissorRockPaper.java`. Python implementations use Python indentation.
Source comments and explanatory docstrings have been removed from the code.

## Run the demonstration

From the project folder:

```sh
python3 tools/setup.py
.venv/bin/python interpreter.py examples/biosensor_clean.mylang
```

The included input is synthetic, with two non-wear intervals, a missing interval,
a spike and a flat artifact. It is not a recording from a person.
Outputs go to `artifacts/biosensor/`: cleaned CSVs, `cleaned_datasets.xlsx`, and
marked PNGs in `figures/`. In VS Code, run the task
**MyLang: biosensor cleaning and graphs**.

Clean your own files:

```sh
.venv/bin/python interpreter.py examples/biosensor_clean.mylang your.csv other.xlsx --output artifacts/my_cleaning --temp-cutoff 28 --interval 1min
```

CSV, XLSX and XLSM input is supported. Column detection looks for timestamp/time,
TAC, temperature and motion names, and standardizes them to `time`, `tac`, `temp`,
`motion`. This pipeline is for the TAC format used in the summer project. For
force or other sensor signals, use the general pandas/Matplotlib tools and adapt
the channel names and cleaning rules to that sensor.

## All nine functions

| Summer name | MyLang name | Purpose |
|---|---|---|
| `loadData` / `load_data` | `loadData(filePath)` | Load and standardize sensor columns |
| `clean_nonwear` | `cleanNonwear(data, tempCutoff=28)` | Mask cold non-wear readings, then time-interpolate |
| `impute_gaps` | `imputeGaps(data, interval=null, maxRows=2000000)` | Add missing timestamps and interpolate sensor values |
| `clean_sensor_jumps` | `cleanSensorJumps(data, jumpMultiplier=6, maxSpikeWidth=120, minFlatWidth=4)` | Correct jumps and suspicious flat intervals |
| `run_quality_controls` | `runQualityControls(filePaths, ...)` | Run the cleaning stages for multiple files |
| `compute_tac_features` | `computeTacFeatures(results)` | Peak, rise/fall rates, correction percentages and noise statistics |
| `plot_final_result` | `plotFinalResult(result, figureFolder, show=false)` | Raw vs cleaned curves with correction markers |
| `export_results` | `exportResults(results, outputFile, figureFolder, observations=null)` | Excel sheets, marked plots and text summaries |
| `run_project` | `runProject(filePaths, ...)` | Run the complete local workflow |

The snake_case names are also available as aliases; keyword arguments use the
camelCase names shown above. `runProject` returns
`results, features, adjustments, notes`.

## Use the stages directly

```text
from mylang.biosensor import loadData, cleanNonwear, imputeGaps, cleanSensorJumps

originalData = loadData("your.csv")
cleanedData = cleanNonwear(originalData, tempCutoff=28)
cleanedData = imputeGaps(cleanedData, interval="1min")
cleanedData = cleanSensorJumps(cleanedData)

if (cleanedData["jump_corrected"].any())
{
    print("Sensor jumps were corrected")
}
```

`examples/biosensor_steps.mylang` demonstrates the stages, feature calculation,
and plotting together.

## Outputs and behavior

The cleaned tables retain three flags: `non_wear`, `gap_imputed`, and
`jump_corrected`. Graphs show the raw trace in gray and cleaned trace in blue,
with orange non-wear, red gap, and purple jump/flat correction markers.
Excel contains `option_1`, `option_2`, etc., `feature_computation`,
`adjustment_summary`, and `clinical_notes`. The last sheet contains the numeric
text summaries and quality notes from the notebook workflow. Pass an
`observations` dictionary keyed by filename for your own written observations.

All functions work on copies. Original tables stay in `result["original"]`.
Excel export retains datetime columns and does not turn your in-memory tables
into strings. The output workbook cannot overwrite a source workbook.

Temperature is assumed to be degrees Celsius, and TAC units are the original
notebook's ug/L. Timestamps are normalized to UTC and stored without a timezone
for Excel compatibility; naive timestamps are treated as UTC. Numeric elapsed
seconds are rejected rather than guessed to be date/time timestamps.

The default settings preserve the notebook's interpolation and end filling,
including non-wear intervals. The widths 120 and 4 are counts of samples, not
seconds. These are the summer project's cleaning heuristics, not a new sensor
calibration or an evaluation of clinical accuracy.

The local version adds checks for empty/all-missing signals, small polynomial
neighborhoods, duplicate timestamps, oversized gap grids and unfamiliar file
names. Irregular off-grid observations are retained. Feature non-wear percentages
use the selected temperature cutoff, correcting the notebook's mismatch between
28 for cleaning and 30 for reporting. Graph filenames include the dataset number
to prevent two same-named inputs from overwriting one another's figure.

References:
[pandas datetime parsing](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.to_datetime.html),
[NumPy polynomial fitting](https://numpy.org/doc/stable/reference/generated/numpy.polyfit.html).
