def format_size(size_bytes: int) -> str:
    """
    Convert size in bytes to human readable format (e.g., B, KB, MB, GB, TB)
    
    Args:
        size_bytes (int): Size in bytes
        
    Returns:
        str: Formatted size string with appropriate unit
    """
    if size_bytes == 0:
        return "0 B"
        
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    size = float(size_bytes)
    unit_index = 0
    
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    
    # Round to 2 decimal places
    if unit_index == 0:  # For bytes, show as integer
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.2f} {units[unit_index]}" 