from enum import Enum
class Role(str, Enum):
    admin = 'admin'
    analyst = 'analyst'
    viewer = 'viewer'
    external = 'external'
class JobStatus(str, Enum):
    queued = 'queued'
    running = 'running'
    completed = 'completed'
    failed = 'failed'
class DeliveryStatus(str, Enum):
    partial = 'partial'
    ready = 'ready'
    stopped = 'stopped'
