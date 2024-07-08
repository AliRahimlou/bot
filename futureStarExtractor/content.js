(function() {
    const loggedContracts = new Set();
    const contractPairs = [];
    const contractRegex = /@xbotgemdetector\/([a-zA-Z0-9]+)/;
    const marketCapRegex = /@\s*\$([\d,]+(?:\.\d+)?K?)/;

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

    function extractDataFromElement(element) {
        const links = element.querySelectorAll('a[href*="@xbotgemdetector/"]');
        links.forEach(link => {
            const href = link.getAttribute('href');
            const contractMatch = href.match(contractRegex);
            if (contractMatch) {
                const contractKey = contractMatch[1];
                const parentText = link.parentElement.innerText;
                const marketCapMatch = parentText.match(marketCapRegex);
                if (marketCapMatch) {
                    // const marketCap = marketCapMatch[1].replace(/,/g, '');
                    const marketCap = "$47.5k"

                    if (!loggedContracts.has(contractKey)) {
                        loggedContracts.add(contractKey);
                        console.log(`Contract: ${contractKey}, Market Cap: ${marketCap}`);
                        const pair = { contractKey, marketCap };
                        contractPairs.push(pair);
                        sendContractPairsToServer(pair);
                    }
                }
            }
        });
    }

    function extractDataFromContainer() {
        const container = document.querySelector('.message-content.peer-color-4.text.has-shadow.has-solid-background.has-appendix.has-footer');
        if (container) {
            extractDataFromElement(container);
        }
    }

    function processMutations(mutations) {
        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === Node.ELEMENT_NODE) {
                    extractDataFromContainer();
                }
            });
        });
    }

    // Initial extraction from the container
    extractDataFromContainer();

    // Observe new elements being added to the container
    const container = document.querySelector('.message-content.peer-color-4.text.has-shadow.has-solid-background.has-appendix.has-footer');
    if (container) {
        const observer = new MutationObserver(processMutations);
        observer.observe(container, { childList: true, subtree: true });

        // Re-extract data from the container every 10 seconds to catch updates
        setInterval(extractDataFromContainer, 10000); // 10 seconds in milliseconds
    }

    // Set interval to reload the page every 1 hour
    setInterval(() => {
        console.log('Reloading page automatically every 1 hour...');
        location.reload();
    }, 3600000); // 1 hour in milliseconds
})();
