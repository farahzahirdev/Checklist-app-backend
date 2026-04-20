"""Service for parsing Excel and CSV files for bulk checklist import."""
import io
from enum import StrEnum
from typing import Optional

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


class FileType(StrEnum):
    """Supported file types."""
    csv = "csv"
    xlsx = "xlsx"
    xls = "xls"


class FileParseError(Exception):
    """Raised when file parsing fails."""
    pass


def detect_file_type(file_name: str) -> FileType:
    """Detect file type from extension."""
    name_lower = file_name.lower()
    if name_lower.endswith('.xlsx'):
        return FileType.xlsx
    elif name_lower.endswith('.csv'):
        return FileType.csv
    elif name_lower.endswith('.xls'):
        return FileType.xls
    else:
        raise FileParseError(f"Unsupported file type: {file_name}")


def normalize_column_ref(col_ref: str) -> tuple[Optional[int], Optional[str]]:
    """
    Convert column reference to (column_index, column_letter).
    Supports: "A", "1", "Column Name"
    Returns: (0-based index, letter) or raises ValueError
    """
    col_ref = col_ref.strip().upper()
    
    # Try A1 format (letters)
    if re.match(r'^[A-Z]+$', col_ref):
        col_index = 0
        for char in col_ref:
            col_index = col_index * 26 + (ord(char) - ord('A') + 1)
        return col_index - 1, col_ref
    
    # Try numeric format
    if col_ref.isdigit():
        col_index = int(col_ref) - 1
        if col_index < 0:
            raise ValueError(f"Invalid column number: {col_ref}")
        # Convert to letter
        col_letter = ""
        num = col_index + 1
        while num > 0:
            num -= 1
            col_letter = chr(num % 26 + ord('A')) + col_letter
            num //= 26
        return col_index, col_letter
    
    # Assume it's a column header name - will be matched during parsing
    return None, col_ref


def parse_csv(content: str | bytes, encoding: str = 'utf-8') -> list[dict]:
    """Parse CSV content and return list of rows as dicts."""
    if not PANDAS_AVAILABLE:
        raise FileParseError("pandas not installed. Install it with: pip install pandas")
    
    if isinstance(content, bytes):
        content = content.decode(encoding)
    
    if not content.strip():
        raise FileParseError("CSV file is empty")
    
    try:
        # Use pandas to read CSV - much more robust than manual parsing
        df = pd.read_csv(io.StringIO(content), dtype=str, na_filter=False)
        
        # Convert to list of dicts, adding row number
        rows = []
        for idx, row in df.iterrows():
            row_dict = {'_row_number': idx + 2}  # +2 because pandas is 0-based, we want 1-based starting from row 2
            row_dict.update(row.to_dict())
            rows.append(row_dict)
        
        return rows
        
    except Exception as e:
        raise FileParseError(f"Failed to parse CSV: {str(e)}")


def parse_xlsx(content: bytes) -> tuple[list[str], list[dict]]:
    """Parse XLSX content and return (headers, rows)."""
    if not PANDAS_AVAILABLE:
        raise FileParseError("pandas not installed. Install it with: pip install pandas")
    
    try:
        # Use pandas to read Excel - much more robust than manual parsing
        df = pd.read_excel(io.BytesIO(content), dtype=str, na_filter=False)
        
        # Get headers
        headers = df.columns.tolist()
        
        # Convert to list of dicts, adding row number
        rows = []
        for idx, row in df.iterrows():
            row_dict = {'_row_number': idx + 2}  # +2 because pandas is 0-based, we want 1-based starting from row 2
            row_dict.update(row.to_dict())
            rows.append(row_dict)
        
        return headers, rows
        
    except Exception as e:
        raise FileParseError(f"Failed to parse XLSX: {str(e)}")


def get_column_value(row: dict, column_spec: str | None, headers: list[str] | None = None) -> Optional[str]:
    """
    Get value from row using column specification.
    Spec can be: "A" (letter), "1" (number), or "Column Name" (header name)
    """
    if not column_spec:
        return None
    
    column_spec = column_spec.strip()
    
    # Try direct key match first (column name/header)
    if column_spec in row:
        value = row.get(column_spec)
        return str(value) if value is not None else None
    
    # Try to find by closest match (case-insensitive)
    lower_spec = column_spec.lower()
    for key in row.keys():
        if key and key != '_row_number' and lower_spec in key.lower():
            value = row.get(key)
            return str(value) if value is not None else None
    
    return None


def parse_file(
    file_content: bytes | str,
    file_name: str,
    encoding: str = 'utf-8'
) -> tuple[list[str], list[dict]]:
    """
    Parse file (Excel or CSV) and return (headers, rows).
    
    Args:
        file_content: Raw file bytes or string
        file_name: Original file name (for type detection)
        encoding: Encoding for text files
    
    Returns:
        (column_headers, rows_as_dicts)
    """
    file_type = detect_file_type(file_name)
    
    if file_type == FileType.csv:
        rows = parse_csv(file_content, encoding)
        headers = list(rows[0].keys()) if rows else []
        headers = [h for h in headers if h != '_row_number']
        return headers, rows
    
    elif file_type in (FileType.xlsx, FileType.xls):
        if isinstance(file_content, str):
            raise FileParseError("XLSX/XLS parsing requires bytes content")
        return parse_xlsx(file_content)
    
    else:
        raise FileParseError(f"Unsupported file type: {file_type}")
