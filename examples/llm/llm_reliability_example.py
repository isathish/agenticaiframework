"""
LLM Reliability Features Example
Demonstrates circuit breaker, retry mechanisms, caching, and fallback chains.
"""

from agenticaiframework import LLMManager
import time

# Mock LLM functions for demonstration
def stable_model(prompt, kwargs):
    """A stable model that always works."""
    return f"Stable response to: {prompt[:50]}..."

def unstable_model(prompt, kwargs):
    """An unstable model that fails sometimes."""
    import random
    if random.random() < 0.7:  # 70% failure rate
        raise Exception("Model temporarily unavailable")
    return f"Unstable response to: {prompt[:50]}..."

def slow_model(prompt, kwargs):
    """A slow but reliable model."""
    time.sleep(0.1)  # Simulate slow response
    return f"Slow response to: {prompt[:50]}..."

def main():
    print("=" * 80)
    print("LLM Reliability Features Example")
    print("=" * 80)
    
    # 1. Create LLM Manager with features
    print("\n1. Creating LLM Manager")
    print("-" * 40)
    
    llm_manager = LLMManager(
        max_retries=3,
        enable_caching=True
    )
    
    # Register multiple models
    llm_manager.register_model(
        "stable",
        stable_model,
        metadata={"provider": "provider_a", "cost_per_token": 0.0001}
    )
    
    llm_manager.register_model(
        "unstable",
        unstable_model,
        metadata={"provider": "provider_b", "cost_per_token": 0.00005}
    )
    
    llm_manager.register_model(
        "slow",
        slow_model,
        metadata={"provider": "provider_c", "cost_per_token": 0.00008}
    )
    
    print(f"Registered models: {llm_manager.list_models()}")
    
    # 2. Basic generation with retry
    print("\n2. Generation with Automatic Retry")
    print("-" * 40)
    
    llm_manager.set_active_model("stable")
    
    prompt = "Explain quantum computing in simple terms"
    response = llm_manager.generate(prompt, temperature=0.7)
    print(f"Prompt: {prompt}")
    print(f"Response: {response}")
    
    # 3. Response caching
    print("\n3. Response Caching")
    print("-" * 40)
    
    print("First request (cache miss):")
    start = time.time()
    response1 = llm_manager.generate(prompt, temperature=0.7)
    time1 = time.time() - start
    print(f"  Time: {time1:.4f}s")
    
    print("\nSecond request (cache hit):")
    start = time.time()
    response2 = llm_manager.generate(prompt, temperature=0.7, use_cache=True)
    time2 = time.time() - start
    print(f"  Time: {time2:.4f}s")
    print(f"  Speedup: {time1/time2:.2f}x")
    
    metrics = llm_manager.get_metrics()
    print(f"\nCache statistics:")
    print(f"  Total requests: {metrics['total_requests']}")
    print(f"  Cache hits: {metrics['cache_hits']}")
    print(f"  Cache hit rate: {metrics['cache_hit_rate']:.2%}")
    
    # 4. Fallback chain
    print("\n4. Fallback Chain for Reliability")
    print("-" * 40)
    
    # Set unstable as primary, with fallbacks
    llm_manager.set_active_model("unstable")
    llm_manager.set_fallback_chain(["stable", "slow"])
    
    print(f"Primary model: {llm_manager.active_model}")
    print(f"Fallback chain: {llm_manager.fallback_chain}")
    
    # Try generation with fallback
    prompt2 = "What is machine learning?"
    print(f"\nGenerating response to: {prompt2}")
    response = llm_manager.generate(prompt2, use_cache=False)
    
    if response:
        print(f"Response received: {response[:80]}...")
    else:
        print("All models failed")
    
    # 5. Circuit breaker pattern
    print("\n5. Circuit Breaker Pattern")
    print("-" * 40)
    
    llm_manager.set_active_model("unstable")
    llm_manager.set_fallback_chain([])  # No fallback for this demo
    
    # Make multiple requests to trigger circuit breaker
    print("Making requests to unstable model:")
    for i in range(8):
        try:
            response = llm_manager.generate(f"Request {i}", use_cache=False)
            if response:
                print(f"  Request {i}: Success")
            else:
                print(f"  Request {i}: Failed")
        except Exception as e:
            print(f"  Request {i}: Exception - {str(e)[:50]}")
    
    # Check circuit breaker state
    model_info = llm_manager.get_model_info("unstable")
    print(f"\nCircuit breaker state: {model_info['circuit_breaker_state']}")
    
    # Reset circuit breaker
    llm_manager.reset_circuit_breaker("unstable")
    print("Circuit breaker reset")
    
    # 6. Model performance comparison
    print("\n6. Model Performance Comparison")
    print("-" * 40)
    
    # Test each model multiple times
    test_prompts = [
        "What is AI?",
        "Explain neural networks",
        "What is deep learning?"
    ]
    
    for model_name in ["stable", "slow"]:
        llm_manager.set_active_model(model_name)
        llm_manager.set_fallback_chain([])
        llm_manager.clear_cache()  # Clear cache for fair comparison
        
        print(f"\nTesting model: {model_name}")
        for prompt in test_prompts:
            llm_manager.generate(prompt, use_cache=False)
        
        info = llm_manager.get_model_info(model_name)
        stats = info['stats']
        print(f"  Requests: {stats['requests']}")
        print(f"  Successes: {stats['successes']}")
        print(f"  Failures: {stats['failures']}")
        print(f"  Avg latency: {stats['avg_latency']:.4f}s")
    
    # 7. Overall metrics
    print("\n7. Overall LLM Manager Metrics")
    print("-" * 40)
    
    metrics = llm_manager.get_metrics()
    print(f"Total requests: {metrics['total_requests']}")
    print(f"Successful: {metrics['successful_requests']}")
    print(f"Failed: {metrics['failed_requests']}")
    print(f"Success rate: {metrics['success_rate']:.2%}")
    print(f"Total retries: {metrics['total_retries']}")
    print(f"Cache hits: {metrics['cache_hits']}")
    print(f"Cache hit rate: {metrics['cache_hit_rate']:.2%}")
    print(f"Total tokens (estimated): {metrics['total_tokens']}")
    
    # 8. Cost estimation
    print("\n8. Cost Estimation")
    print("-" * 40)
    
    total_cost = 0.0
    for model_name in llm_manager.list_models():
        info = llm_manager.get_model_info(model_name)
        if info:
            requests = info['stats']['successes']
            cost_per_token = info['metadata'].get('cost_per_token', 0)
            # Rough estimate: 50 tokens per successful request
            estimated_cost = requests * 50 * cost_per_token
            total_cost += estimated_cost
            
            print(f"{model_name}:")
            print(f"  Successful requests: {requests}")
            print(f"  Cost per token: ${cost_per_token:.6f}")
            print(f"  Estimated cost: ${estimated_cost:.4f}")
    
    print(f"\nTotal estimated cost: ${total_cost:.4f}")
    
    # 9. Cache management
    print("\n9. Cache Management")
    print("-" * 40)
    
    print(f"Cache size before clear: {len(llm_manager.cache)}")
    llm_manager.clear_cache()
    print(f"Cache size after clear: {len(llm_manager.cache)}")
    
    # Rebuild cache
    llm_manager.set_active_model("stable")
    for i in range(5):
        llm_manager.generate(f"Test prompt {i}")
    
    print(f"Cache rebuilt with {len(llm_manager.cache)} entries")
    
    print("\n" + "=" * 80)
    print("LLM Reliability Features Example Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
