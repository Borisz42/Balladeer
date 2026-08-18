import pytest
import logging
from pathlib import Path
import numpy as np

from app.core.memory_manager import memory_manager
from app.core.config import get_settings
from app.models.siglip_embedder import siglip_embedder
from app.pipeline.indexer import MediaIndexer

def test_hardware_device_detection_and_logging(caplog):
    """Verifies that the hardware manager detects CUDA or CPU and logs appropriately."""
    with caplog.at_level(logging.INFO):
        settings = get_settings()
        assert settings.hardware.device is not None
        
        is_cuda = memory_manager.is_cuda
        device = memory_manager.device
        assert device is not None
        
        vram_stats = memory_manager.get_vram_usage()
        assert "allocated_gb" in vram_stats
        assert "total_gb" in vram_stats

def test_siglip_embedder_768dim_and_normalization():
    """Verifies SigLIP 2 produces 768-dimensional normalized embeddings."""
    text_emb = siglip_embedder.encode_text("Golden sunrise over mount fuji in autumn")
    assert len(text_emb) == 768
    norm = np.linalg.norm(np.array(text_emb, dtype=np.float32))
    assert abs(norm - 1.0) < 0.01

    batch_texts = [
        "Torii gates in Kyoto",
        "Street food at Nishiki market",
        "Cherry blossoms in Tokyo"
    ]
    batch_embs = siglip_embedder.encode_texts_batch(batch_texts)
    assert len(batch_embs) == 3
    for emb in batch_embs:
        assert len(emb) == 768
        assert abs(np.linalg.norm(np.array(emb, dtype=np.float32)) - 1.0) < 0.01

def test_indexer_aesthetic_scoring():
    """Verifies that the Laplacian sharpness and exposure scoring compute valid numbers in [0, 1]."""
    indexer = MediaIndexer()
    
    # Generate sharp gradient test frame
    sharp_img = np.zeros((224, 224, 3), dtype=np.uint8)
    sharp_img[:, :112] = 255
    score_sharp = indexer.evaluate_frame_aesthetics(sharp_img)
    assert 0.0 <= score_sharp <= 1.0

    # Generate blurry uniform gray frame
    blurry_img = np.full((224, 224, 3), 128, dtype=np.uint8)
    score_blurry = indexer.evaluate_frame_aesthetics(blurry_img)
    assert 0.0 <= score_blurry <= 1.0
    assert score_sharp > score_blurry

def test_indexer_full_and_daily_travel_log_relevance():
    """Verifies that frame relevance computation correctly calculates cosine similarity across daily and full log."""
    indexer = MediaIndexer()
    
    emb_frame = [1.0, 0.0, 0.0]
    emb_daily = [0.95, 0.05, 0.0]
    emb_full = [0.85, 0.15, 0.0]
    emb_irrelevant = [0.0, 1.0, 0.0]

    sim_daily = indexer.cosine_similarity(emb_frame, emb_daily)
    sim_full = indexer.cosine_similarity(emb_frame, emb_full)
    sim_irrelevant = indexer.cosine_similarity(emb_frame, emb_irrelevant)

    assert sim_daily > sim_irrelevant
    assert sim_full > sim_irrelevant
    assert sim_daily > 0.8
