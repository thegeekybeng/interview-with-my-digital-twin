import re

class PIIShield:
    """Automated PII, IP address, hardware model, and network topology generalizer."""
    
    # Generalization & Security Regex Patterns
    PATTERNS = [
        # Private / Tailscale IP Addresses
        (r'\b(?:10|127|172\.(?:1[6-9]|2[0-9]|3[01])|192\.168|100\.\d{1,3})\.\d{1,3}\.\d{1,3}\b', '[REDACTED_INTERNAL_IP]'),
        
        # Specific Hardware Device Models & Brand Names -> Generalized Edge Terms
        (r'(?i)\bMac\s*Mini\s*M4\s*Pro\b', 'Edge Inference Host'),
        (r'(?i)\bM4\s*Pro\b', 'Edge Compute Device'),
        (r'(?i)\bMacBook\s*Air\b', 'Primary Workstation'),
        (r'(?i)\bUGreen\s*NAS(\s*DXP4800)?\b', 'Network Attached Storage Node'),
        (r'(?i)\bNVIDIA\s*GPU(\s*and\s*Intel\s*Xeon)?\b', 'Hardware Acceleration Engine'),
        (r'(?i)\bIntel\s*(Xeon|Core\s*i[79])\b', 'High-Performance CPU Host'),

        # Platform Architecture & Acceleration Vendor Branding -> Generalized Tensor Terms
        (r'(?i)\bApple\s*Silicon(\s*Metal)?\b', 'Hardware Accelerated Architecture'),
        (r'(?i)\bPyTorch\s*MPS(\s*acceleration)?\b', 'Hardware Accelerated Tensor Backend'),
        (r'(?i)\bMPS\s*acceleration\b', 'Hardware Accelerated Tensor Backend'),
        (r'(?i)\bCUDA\s*(GPUs|acceleration)?\b', 'Hardware Accelerated GPU/NPU Engine'),
        
        # Local Absolute File Paths
        (r'/Users/[a-zA-Z0-9_-]+/[^\s]+', '[REDACTED_LOCAL_PATH]'),
        (r'/home/[a-zA-Z0-9_-]+/[^\s]+', '[REDACTED_LOCAL_PATH]'),
        
        # Phone Numbers & Personal Emails
        (r'\+?\b(?:65\s*)?[89]\d{3}\s*\d{4}\b', '[REDACTED_PHONE]'),
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[REDACTED_EMAIL]'),

        # MAC Addresses & Credentials
        (r'\b(?:[0-9A-Fa-f]{2}[:-]){5}(?:[0-9A-Fa-f]{2})\b', '[REDACTED_MAC_ADDR]'),
        (r'(?i)(password|secret|api[_-]?key|token)\s*=\s*[\'"][^\'"]+[\'"]', r'\1=[REDACTED_SECRET]'),
    ]

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        if not text:
            return text
            
        sanitized = text
        for pattern, replacement in cls.PATTERNS:
            sanitized = re.sub(pattern, replacement, sanitized)
            
        return sanitized
