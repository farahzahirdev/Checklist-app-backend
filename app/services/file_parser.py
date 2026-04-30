"""Service for parsing Excel and CSV files for bulk checklist import."""
import io
import re
from enum import StrEnum
from typing import Optional

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


def _normalize_excel_headers(columns) -> list[str]:
    """Flatten Excel column headers, including MultiIndex from merged header rows."""
    headers: list[str] = []
    if hasattr(columns, 'levels') and getattr(columns, 'nlevels', 1) > 1:
        for col in columns:
            if isinstance(col, tuple):
                parts = [
                    str(part).strip()
                    for part in col
                    if part is not None and (not isinstance(part, float) or not pd.isna(part))
                ]
                if len(parts) == 0:
                    headers.append("")
                elif len(parts) == 1:
                    headers.append(parts[0])
                else:
                    top, bottom = parts[0], parts[-1]
                    if bottom.isdigit():
                        headers.append(bottom)
                    elif top and bottom and top != bottom:
                        headers.append(f"{top} {bottom}")
                    else:
                        headers.append(bottom or top)
            else:
                headers.append(str(col).strip())
    else:
        headers = [str(col).strip() for col in columns]
    return headers


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
        
        # Check for two-row header format (like user's CSV)
        if len(df) >= 2:
            first_row = df.iloc[0].fillna('').astype(str)
            second_row = df.iloc[1].fillna('').astype(str)
            
            # Check if second row contains column letters (A, B, C, etc.)
            header_letters = [col.strip() for col in second_row if col.strip() and col.strip().isalpha()]
            if len(header_letters) >= 3:  # Likely two-row header format
                
                # Create mapping from letter to actual column name
                column_mapping = {}
                for i, letter in enumerate(header_letters):
                    if i < len(first_row):
                        column_mapping[letter] = str(first_row.iloc[i])
                
                # Apply mapping to data rows (skip first two header rows)
                rows = []
                for idx in range(2, len(df)):  # Start from row 3 (index 2)
                    row_dict = {'_row_number': idx + 2}
                    raw_row = df.iloc[idx].fillna('').astype(str)
                    
                    # Map letter columns to actual names
                    for letter, actual_name in column_mapping.items():
                        if actual_name and actual_name.strip():
                            row_dict[actual_name] = raw_row.iloc[i] if i < len(raw_row) else ''
                    
                    # Add remaining columns that don't have letter mapping
                    for i, (col_name, value) in enumerate(raw_row.items()):
                        if col_name not in row_dict:
                            row_dict[col_name] = value
                    
                    rows.append(row_dict)
                
                # Create headers from the mapping and any additional columns
                headers = []
                # Add mapped column names
                for actual_name in column_mapping.values():
                    if actual_name and actual_name.strip() and actual_name not in headers:
                        headers.append(actual_name)
                
                # Add any remaining column names from the data
                if rows:
                    for col_name in rows[0].keys():
                        if col_name not in headers and col_name != '_row_number':
                            headers.append(col_name)
                
                return headers, rows
        
        # Default parsing for normal CSV
        # Convert to list of dicts, adding row number
        rows = []
        for idx, row in df.iterrows():
            row_dict = {'_row_number': idx + 2}  # +2 because pandas is 0-based, we want 1-based starting from row 2
            row_dict.update(row.to_dict())
            rows.append(row_dict)
        
        if rows:
            headers = list(rows[0].keys())
            headers = [h for h in headers if h != '_row_number']
        else:
            headers = []
        return headers, rows
        
    except Exception as e:
        raise FileParseError(f"Failed to parse CSV: {str(e)}")


def parse_xlsx(content: bytes) -> tuple[list[str], list[dict]]:
    """Parse XLSX content and return (headers, rows)."""
    if not PANDAS_AVAILABLE:
        raise FileParseError("pandas not installed. Install it with: pip install pandas")
    
    try:
        # Use pandas to read Excel - much more robust than manual parsing
        df = pd.read_excel(io.BytesIO(content), dtype=str, na_filter=False)
        
        # Get headers, flattening multi-row header metadata if present
        headers = _normalize_excel_headers(df.columns)
        
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
    """Get value from a row using column letter or header name."""
    if not column_spec:
        return None
    
    # If column_spec is a letter (like "A", "B") and headers are provided, map to header name
    if column_spec.isalpha() and len(column_spec) <= 3:
        if headers:
            idx = ord(column_spec.upper()) - ord('A')
            if 0 <= idx < len(headers):
                header = headers[idx]
                return row.get(header)
        # fallback: try direct key
        return row.get(column_spec.upper())
    
    # If column_spec is a header name, find the matching column
    if headers:
        # Try exact match first
        if column_spec in headers:
            return row.get(column_spec)
        
        # Try case-insensitive match
        for header in headers:
            if header.lower() == column_spec.lower():
                return row.get(header)
        
        # Try normalized match (remove spaces, underscores, and convert to lowercase)
        normalized_spec = column_spec.lower().replace(" ", "").replace("_", "")
        for header in headers:
            normalized_header = header.lower().replace(" ", "").replace("_", "")
            if normalized_header == normalized_spec:
                return row.get(header)
    
    # Fallback: try column_spec as key directly
    return row.get(column_spec)


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
        headers, rows = parse_csv(file_content, encoding)
        return headers, rows
    
    elif file_type in (FileType.xlsx, FileType.xls):
        if isinstance(file_content, str):
            raise FileParseError("XLSX/XLS parsing requires bytes content")
        return parse_xlsx(file_content)
    
    else:
        raise FileParseError(f"Unsupported file type: {file_type}")
