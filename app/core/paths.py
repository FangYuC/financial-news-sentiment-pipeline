from pathlib import Path


class PathManager:
    def __init__(self, project_root: Path = None, ticker: str = None):

        self.project_root = project_root or Path(__file__).resolve().parents[2]
        self.ticker = ticker.upper() if ticker else None

        # =========================
        # BASE DIRS
        # =========================
        self.data = self.project_root / "data"

        self.raw = self.data / "raw"
        self.processed = self.data / "processed"
        self.features = self.data / "features"
        self.labels = self.data / "labels"

        # =========================
        # PROCESSED
        # =========================
        self.stage1 = self.processed / "stage1"
        self.stage2 = self.processed / "stage2"
        self.stage3 = self.processed / "stage3"
        # =========================
        # FEATURES
        # =========================
        self.merged = self.features / "merged"

    # =========================
    # HELPER METHODS
    # =========================
    def stage1_file(self):
        return self.stage1 / f"{self.ticker}.csv"

    def stage2_file(self):
        return self.stage2 / f"{self.ticker}.csv"

    def stage3_file(self):
        return self.stage3 / f"{self.ticker}.csv"

    def merged_file(self):
        return self.merged / f"{self.ticker}_dataset.csv"