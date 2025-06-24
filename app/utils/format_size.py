def get_size_in_gb(size_bytes: int) -> float:
    """Convert bytes to gigabytes"""
    return size_bytes / (1024 * 1024 * 1024)

def get_size_in_bytes(size_gb: float) -> int:
    """Convert gigabytes to bytes"""
    return int(size_gb * 1024 * 1024 * 1024)

def format_size(size_bytes: int) -> str:
    """
    Convert size in bytes to human readable format (e.g., B, KB, MB, GB, TB)
    
    Args:
        size_bytes (int): Size in bytes
        
    Returns:
        str: Formatted size string with appropriate unit
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB" 
