"""Unit test for export module and platform-wise sheets/CSVs."""

from pathlib import Path
import pandas as pd
from research.models import PlatformEnum, Product
from research.storage.export import export_reports


def test_export_reports_platform_tabs(tmp_path):
    p_amz = Product(
        platform=PlatformEnum.AMAZON,
        product_id="B001",
        title="Amazon Item",
        url="https://amazon.in/dp/B001",
        price=500.0,
    )
    p_fk = Product(
        platform=PlatformEnum.FLIPKART,
        product_id="FK001",
        title="Flipkart Item",
        url="https://flipkart.com/p/FK001",
        price=400.0,
    )
    p_ms = Product(
        platform=PlatformEnum.MEESHO,
        product_id="MS001",
        title="Meesho Item",
        url="https://meesho.com/p/MS001",
        price=300.0,
    )

    all_prods = [p_amz, p_fk, p_ms]
    
    from research.config import Config
    cfg = Config()
    cfg.output.dir = str(tmp_path / "reports")

    db_test = str(tmp_path / "test.db")
    out_dir = export_reports("test_query", all_prods, all_prods, cfg=cfg, generate_xlsx=True, db_file=db_test)

    # Check platform-wise CSVs exist
    assert (out_dir / "report.csv").exists()
    assert (out_dir / "report_amazon.csv").exists()
    assert (out_dir / "report_flipkart.csv").exists()
    assert (out_dir / "report_meesho.csv").exists()
    assert (out_dir / "report_all.csv").exists()

    # Check Excel multi-tab workbook
    xlsx_path = out_dir / "report.xlsx"
    assert xlsx_path.exists()

    xl = pd.ExcelFile(xlsx_path)
    sheet_names = xl.sheet_names
    assert "All_Ranked" in sheet_names
    assert "Amazon" in sheet_names
    assert "Flipkart" in sheet_names
    assert "Meesho" in sheet_names
    assert "All_Scraped_Raw" in sheet_names

    df_amz = pd.read_excel(xlsx_path, sheet_name="Amazon")
    assert len(df_amz) == 1
    assert df_amz.iloc[0]["product_id"] == "B001"
