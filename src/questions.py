"""
Curated benchmark questions for 'The Relay' evaluation.
Includes answerable questions for each paper, cross-paper questions,
unanswerable out-of-scope questions, and adversarial misleading questions.
"""

EVALUATION_QUESTIONS = [
    {
        "id": "q01",
        "category": "Attention",
        "question": "Why did the authors scale the dot product by 1/sqrt(d_k) in Scaled Dot-Product Attention?",
        "expected_answerable": True,
        "target_paper": "1706.03762v7",
        "key_phrases": ["dot product grows large", "small gradients", "softmax"]
    },
    {
        "id": "q02",
        "category": "Attention",
        "question": "What exact formula is used for Positional Encoding in the Transformer architecture?",
        "expected_answerable": True,
        "target_paper": "1706.03762v7",
        "key_phrases": ["sin", "cos", "10000", "2i"]
    },
    {
        "id": "q03",
        "category": "Attention",
        "question": "What were the warmup steps and optimizer parameters used for training the Transformer base model?",
        "expected_answerable": True,
        "target_paper": "1706.03762v7",
        "key_phrases": ["warmup_steps = 4000", "Adam", "beta1 = 0.9", "beta2 = 0.98"]
    },
    {
        "id": "q04",
        "category": "Attention",
        "question": "How many layers and attention heads are configured in the Transformer Big model versus the Base model?",
        "expected_answerable": True,
        "target_paper": "1706.03762v7",
        "key_phrases": ["h = 16", "h = 8", "d_model = 1024", "d_model = 512"]
    },
    {
        "id": "q05",
        "category": "Moshi",
        "question": "What is the frame rate and operational bitrate of the Mimi neural audio codec used in Moshi?",
        "expected_answerable": True,
        "target_paper": "2410.00037v1",
        "key_phrases": ["12.5 Hz", "1.1 kbps", "Mimi", "RVQ"]
    },
    {
        "id": "q06",
        "category": "Moshi",
        "question": "How does Moshi's Inner Monologue mechanism work to reduce latency during spoken dialogue?",
        "expected_answerable": True,
        "target_paper": "2410.00037v1",
        "key_phrases": ["inner monologue", "text tokens", "ahead of audio", "time delay"]
    },
    {
        "id": "q07",
        "category": "Moshi",
        "question": "What are the two separate audio streams modeled concurrently by Moshi during full-duplex conversation?",
        "expected_answerable": True,
        "target_paper": "2410.00037v1",
        "key_phrases": ["user stream", "system stream", "full-duplex", "parallel"]
    },
    {
        "id": "q08",
        "category": "Moshi",
        "question": "What quantization technique and number of codebooks are used in the Mimi codec?",
        "expected_answerable": True,
        "target_paper": "2410.00037v1",
        "key_phrases": ["Residual Vector Quantization", "RVQ", "8 codebooks", "32 codebooks"]
    },
    {
        "id": "q09",
        "category": "Dynamic Chunking",
        "question": "How does Dynamic Chunking (H-Net) eliminate the need for fixed subword tokenizers like BPE?",
        "expected_answerable": True,
        "target_paper": "2507.07955v2",
        "key_phrases": ["tokenizer-free", "raw bytes", "hierarchical", "adaptive boundaries"]
    },
    {
        "id": "q10",
        "category": "Dynamic Chunking",
        "question": "On which modalities or languages does H-Net show the largest gains (e.g. ~4x data efficiency) over BPE?",
        "expected_answerable": True,
        "target_paper": "2507.07955v2",
        "key_phrases": ["Chinese", "computer code", "DNA sequences", "character-level"]
    },
    {
        "id": "q11",
        "category": "Dynamic Chunking",
        "question": "How does the dynamic chunking boundary predictor decide when to close a chunk in H-Net?",
        "expected_answerable": True,
        "target_paper": "2507.07955v2",
        "key_phrases": ["boundary", "probability", "threshold", "segmentation"]
    },
    {
        "id": "q12",
        "category": "Dynamic Chunking",
        "question": "How does multi-stage dynamic chunking achieve higher levels of temporal abstraction in sequence modeling?",
        "expected_answerable": True,
        "target_paper": "2507.07955v2",
        "key_phrases": ["multi-stage", "hierarchy", "coarse-grained", "scaling"]
    },
    {
        "id": "q13",
        "category": "Cross-Paper",
        "question": "Compare the tokenization approach of 'Attention Is All You Need' with the representation used in 'Dynamic Chunking'.",
        "expected_answerable": True,
        "target_paper": "Cross",
        "key_phrases": ["BPE", "byte-pair", "tokenizer-free", "H-Net", "raw bytes"]
    },
    {
        "id": "q14",
        "category": "Cross-Paper",
        "question": "How does Moshi's streaming audio frame chunking compare with H-Net's dynamic chunking boundary mechanism?",
        "expected_answerable": True,
        "target_paper": "Cross",
        "key_phrases": ["fixed 12.5 Hz frame rate", "adaptive learned boundaries", "temporal"]
    },
    {
        "id": "q15",
        "category": "Unanswerable",
        "question": "What quantum computing algorithm is recommended by the authors to accelerate Transformer matrix multiplication?",
        "expected_answerable": False,
        "target_paper": "None",
        "key_phrases": ["do not discuss", "does not contain"]
    },
    {
        "id": "q16",
        "category": "Unanswerable",
        "question": "How does CRISPR Cas9 gene editing compare to the Mimi audio codec in biological sequence benchmarks?",
        "expected_answerable": False,
        "target_paper": "None",
        "key_phrases": ["do not discuss", "does not contain"]
    },
    {
        "id": "q17",
        "category": "Unanswerable",
        "question": "What consensus mechanism does Moshi use to validate cryptocurrency transactions on the blockchain?",
        "expected_answerable": False,
        "target_paper": "None",
        "key_phrases": ["do not discuss", "does not contain"]
    },
    {
        "id": "q18",
        "category": "Adversarial",
        "question": "What subword BPE tokenizer vocabulary size was used to train the byte-level H-Net in Dynamic Chunking?",
        "expected_answerable": True, # Should explain that H-Net is tokenizer-free and uses byte level without BPE vocabulary
        "target_paper": "2507.07955v2",
        "key_phrases": ["does not use BPE", "tokenizer-free", "byte-level", "256 byte vocabulary"]
    }
]
