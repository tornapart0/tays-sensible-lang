import contextlib
import io
import tempfile
import unittest
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
from mylang.biosensor import loadData, cleanNonwear, imputeGaps, cleanSensorJumps
from mylang.biosensor import runQualityControls, computeTacFeatures, exportResults


def sampleData(values, temperatures=None):
    return pd.DataFrame({"time": pd.date_range("2026-07-01", periods=len(values), freq="min"),
                         "tac": values, "temp": temperatures or [32] * len(values),
                         "motion": [0.1] * len(values)})


class BiosensorTests(unittest.TestCase):
    def test_load_and_column_detection(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.csv"
            pd.DataFrame({"Timestamp": ["2026-07-01T01:00:00-04:00", "bad", "2026-07-01T01:00:00-04:00"],
                          "TAC signal": [1, 2, 3], "Skin Temp": [32, 32, 32], "Motion level": [0, 0, 1]}).to_csv(path, index=False)
            data = loadData(path)
            self.assertEqual(len(data), 1)
            self.assertEqual(data.iloc[0]["tac"], 3)
            self.assertEqual(data.iloc[0]["time"], pd.Timestamp("2026-07-01 05:00:00"))
            data.to_excel(Path(folder) / "sample.xlsx", index=False)
            assert_frame_equal(loadData(Path(folder) / "sample.xlsx"), data, check_dtype=False)

    def test_nonwear_copy_and_interpolation(self):
        original = sampleData([0, 100, 2], [32, 26, 32])
        saved = original.copy(deep=True)
        cleaned = cleanNonwear(original)
        self.assertTrue(cleaned.loc[1, "non_wear"])
        self.assertEqual(cleaned.loc[1, "tac"], 1)
        assert_frame_equal(original, saved)

    def test_gaps_preserve_irregular_observations(self):
        data = sampleData([0, 1, 3, 3.5])
        data["time"] = pd.to_datetime(["2026-07-01 00:00", "2026-07-01 00:01", "2026-07-01 00:03", "2026-07-01 00:03:30"], format="mixed")
        cleaned = imputeGaps(data, "1min", maxRows=5)
        self.assertEqual(len(cleaned), 5)
        self.assertEqual(cleaned["gap_imputed"].sum(), 1)
        self.assertEqual(cleaned.loc[2, "tac"], 2)
        self.assertEqual(cleaned.loc[4, "time"], data.loc[3, "time"])
        with self.assertRaisesRegex(ValueError, 'too large'):
            imputeGaps(data, "1ns", maxRows=100)

    def test_spike_correction(self):
        original = sampleData([0, 1, 2, 3, 4, 40, 6, 7, 8, 9])
        cleaned = cleanSensorJumps(original)
        self.assertTrue(cleaned.loc[5, "jump_corrected"])
        self.assertAlmostEqual(cleaned.loc[5, "tac"], 5)
        self.assertEqual(original.loc[5, "tac"], 40)

    def test_flat_artifact_correction(self):
        data = sampleData([0, 1, 2, 3, 4, 40, 40, 40, 40, 40, 40, 40, 12, 13, 14, 15, 16])
        cleaned = cleanSensorJumps(data)
        self.assertTrue(cleaned.loc[6:11, "jump_corrected"].all())
        self.assertTrue(cleaned.loc[6:11, "tac"].lt(20).all())

    def test_missing_constant_and_single_point(self):
        for values in [[np.nan, np.nan], [2, 2, 2, 2], [3], []]:
            with self.subTest(values=values):
                data = sampleData(values)
                cleaned = cleanSensorJumps(data)
                self.assertEqual(len(cleaned), len(data))
                self.assertFalse(cleaned["jump_corrected"].any())
        cleaned = cleanNonwear(sampleData([1, 2], [25, 25]))
        cleaned = cleanSensorJumps(imputeGaps(cleaned))
        self.assertTrue(cleaned["tac"].isna().all())
        self.assertTrue(cleaned["non_wear"].all())

    def test_features_use_configured_temperature(self):
        data = sampleData([0, 2, 0], [29, 29, 29])
        result = {"name": "sample", "original": data, "final": data, "temp_cutoff": 28}
        features = computeTacFeatures([result])
        self.assertEqual(features.loc[0, "peak_tac"], 2)
        self.assertEqual(features.loc[0, "rise_rate"], 2)
        self.assertEqual(features.loc[0, "fall_rate"], 2)
        self.assertEqual(features.loc[0, "percent_non_wear"], 0)

    def test_export_keeps_datetimes_and_writes_flags(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            source = Path(folder) / "raw.csv"
            sampleData([0, 100, 2, 3, 4], [32, 26, 32, 32, 32]).to_csv(source, index=False)
            results = runQualityControls([source])
            saved = results[0]["final"].copy(deep=True)
            output = Path(folder) / "cleaned.xlsx"
            features, adjustments, notes = exportResults(results, output, Path(folder) / "graphs")
            assert_frame_equal(results[0]["final"], saved)
            with pd.ExcelFile(output) as book:
                self.assertEqual(book.sheet_names, ['option_1', 'feature_computation', 'adjustment_summary', 'clinical_notes'])
            self.assertEqual(adjustments.loc[0, "non_wear_adjusted_rows"], 1)
            self.assertEqual(notes.loc[0, "personal observations"], "")
            self.assertEqual(len(list((Path(folder) / "graphs").glob('*.png'))), 1)

    def test_no_valid_signal_exports_without_crashing(self):
        with tempfile.TemporaryDirectory() as folder:
            data = sampleData([np.nan, np.nan])
            result = {"number": 1, "name": "missing.csv", "original": data, "final": data}
            features, adjustments, notes = exportResults([result], Path(folder) / "out.xlsx", Path(folder) / "graphs")
            self.assertEqual(features.loc[0, "error"], 'No valid TAC data')
            self.assertEqual(notes.loc[0, "clinical_insight"], 'No valid TAC data')

    def test_input_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'raw.xlsx'
            data = sampleData([1, 2])
            data.to_excel(source, index=False)
            original = source.read_bytes()
            result = {"number": 1, "name": "raw.xlsx", "source": str(source), "original": data, "final": data}
            with self.assertRaisesRegex(ValueError, 'different from the original'):
                exportResults([result], source, Path(folder) / 'graphs')
            self.assertEqual(source.read_bytes(), original)
