(function() {
    const loggedTokens = new Set();
    const contractPairs = [];
    const tokenRegex = /https:\/\/solscan\.io\/token\/([a-zA-Z0-9]+)/;
    const marketCapRegex = /Current Market Cap:\s*\$([\d,]+)/;

    async function sendContractPairsToServer(pair) {
        try {
            const response = await fetch('http://127.0.0.1:5001/save_contracts', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(pair),
            });
            const result = await response.json();
            console.log(`Server response: ${JSON.stringify(result)}`);
        } catch (error) {
            console.error('Error sending contract pair to server:', error);
        }
    }

    (function reloadEveryFiveMinutes() {
        // Function to reload the page
        function reloadPage() {
            console.log('Reloading page automatically every 2 hours...');
            location.reload();
        }
    
        // Set interval to reload the page every 2 hours
        setInterval(reloadPage, 7200000); // 2 hours in milliseconds
    })();

    function extractDataFromElement(element) {
        const textContent = element.innerHTML;

        // Extract market cap
        const marketCapMatch = textContent.match(marketCapRegex);

        // Extract token address
        const tokenMatch = textContent.match(tokenRegex);

        if (marketCapMatch && tokenMatch && marketCapMatch[1] && tokenMatch[1]) {
            const marketCap = marketCapMatch[1].replace(/,/g, '');
            const tokenAddress = tokenMatch[1];

            if (!loggedTokens.has(tokenAddress)) {
                console.log(`Token Address: ${tokenAddress}, Current Market Cap: ${marketCap}`);
                loggedTokens.add(tokenAddress);
                const pair = { tokenAddress, marketCap };
                contractPairs.push(pair);
                sendContractPairsToServer(pair);
            }
        }
    }

    function extractDataFromElements(elements) {
        elements.forEach((element) => {
            if (element.classList && element.classList.contains('text-content') && element.classList.contains('clearfix')) {
                extractDataFromElement(element);
            }
            element.querySelectorAll('.text-content.clearfix').forEach(subElement => {
                extractDataFromElement(subElement);
            });
        });
    }

    // Initial extraction from existing elements
    const elements = document.querySelectorAll('.text-content.clearfix');
    extractDataFromElements(elements);

    // Observe new elements being added to the DOM
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === Node.ELEMENT_NODE) {
                    extractDataFromElements([node]);
                }
            });
        });
    });

    observer.observe(document.body, { childList: true, subtree: true });
})();
