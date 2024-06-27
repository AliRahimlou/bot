(function() {
    const contractPairs = [];
    const contractRegex = /\b([a-zA-Z0-9]{32,})\b/;
    const statusRegex = /Status:\s*(Rich Dev|GEM)/;
    const marketCapRegex = /Market Cap:\s*([^\n\r]+)/;

    async function sendContractPairsToServer(pair) {
        try {
            const response = await fetch('http://127.0.0.1:5000/save_contracts', {
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
    

    function extractDataFromElement(element) {
        const textContent = element.innerText;

        if (statusRegex.test(textContent)) {
            const contractMatches = textContent.match(contractRegex);
            const marketCapMatch = textContent.match(marketCapRegex);

            if (contractMatches && marketCapMatch) {
                const marketCap = marketCapMatch[1].trim();
                
                contractMatches.forEach(contractMatch => {
                    const contractKey = contractMatch.trim();
                    const pair = { contractKey, marketCap };

                    if (!contractPairs.some(item => item.contractKey === contractKey)) {
                        contractPairs.push(pair);
                        console.log(`Contract: ${contractKey}, Market Cap: ${marketCap}`);
                        sendContractPairsToServer(pair);
                    }
                });
            }
        }
    }

    function extractDataFromElements(elements) {
        elements.forEach((element) => {
            if (element.classList && element.classList.contains('text-content') && element.classList.contains('clearfix') && element.classList.contains('with-meta')) {
                extractDataFromElement(element);
            }
            element.querySelectorAll('.text-content.clearfix.with-meta').forEach(subElement => {
                extractDataFromElement(subElement);
            });
        });
    }

    // Initial extraction from existing elements
    const elements = document.querySelectorAll('.text-content.clearfix.with-meta');
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
