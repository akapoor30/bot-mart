// frontend/app.js

document.getElementById('searchForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const product = document.getElementById('productInput').value.trim();
    const pincode = document.getElementById('pincodeInput').value.trim();
    
    if (!product || !pincode) return;

    // UI State Management
    const searchForm = document.getElementById('search-panel');
    const loadingState = document.getElementById('loadingState');
    const resultsContainer = document.getElementById('results-container');
    const searchBtn = document.getElementById('searchBtn');
    
    searchBtn.disabled = true;
    loadingState.style.display = 'flex';
    resultsContainer.style.display = 'none';

    try {
        // Fetch from local FastAPI backend
        const response = await fetch(`http://127.0.0.1:8000/compare?item=${encodeURIComponent(product)}&pincode=${encodeURIComponent(pincode)}`);
        
        if (!response.ok) {
            throw new Error(`Server responded with status: ${response.status}`);
        }
        
        const data = await response.json();
        
        renderResults(data);
        
        // Show results
        loadingState.style.display = 'none';
        resultsContainer.style.display = 'block';

    } catch (error) {
        console.error("Fetch error:", error);
        loadingState.innerHTML = `
            <div style="color: #ef4444; text-align: center;">
                <h3>Connection Error</h3>
                <p style="margin-top: 0.5rem; font-size: 0.9rem;">Could not connect to the Delivery Bot backend.</p>
                <p style="font-size: 0.8rem; opacity: 0.7; margin-top: 0.5rem;">Ensure Uvicorn is running on port 8000 and CORS is configured.</p>
            </div>
        `;
    } finally {
        searchBtn.disabled = false;
    }
});

function renderResults(data) {
    const winnerWrapper = document.getElementById('winnerCardWrapper');
    const othersList = document.getElementById('otherResultsList');
    
    winnerWrapper.innerHTML = '';
    othersList.innerHTML = '';

    const cheapest = data.cheapest_option;
    const allResults = data.all_results || [];

    // Render Winner Card if it exists
    if (cheapest) {
        winnerWrapper.innerHTML = createCardHTML(cheapest, true);
    } else {
        winnerWrapper.innerHTML = `
            <div class="card failed glass-panel" style="width: 100%;">
                <p class="failed-text">No successful results found across any store.</p>
            </div>
        `;
    }

    // Render Other Results
    allResults.forEach(result => {
        // Skip rendering the exact winner again in the 'others' list
        if (cheapest && result.store === cheapest.store && result.name === cheapest.name && result.price === cheapest.price) {
            return;
        }
        othersList.innerHTML += createCardHTML(result, false);
    });
}

function createCardHTML(item, isWinner) {
    const storeClass = `store-${item.store ? item.store.toLowerCase() : 'unknown'}`;
    const cardClass = isWinner ? 'card winner-card' : 'card';
    
    if (item.status === 'success') {
        return `
            <div class="${cardClass}">
                <div class="product-info">
                    <span class="store-badge ${storeClass}">${item.store}</span>
                    <h3>${item.name}</h3>
                </div>
                <div class="price-container">
                    <div class="price"><span>₹</span>${item.price}</div>
                </div>
            </div>
        `;
    } else {
        // Failed card
        return `
            <div class="card failed">
                <div class="product-info">
                    <span class="store-badge ${storeClass}">${item.store || 'Unknown'}</span>
                    <h3>Scrape Failed</h3>
                    <p class="failed-text">${item.error || 'Unknown error occurred'}</p>
                </div>
                <div class="price-container">
                    <div class="price" style="color: #94a3b8;">--</div>
                </div>
            </div>
        `;
    }
}
