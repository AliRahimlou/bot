(function() {
    const nameContractPairs = [];
    const nameRegex = /Name:\s*(.*\(.*\) \(.*GEM\))/;
    const contractRegex = /Contract:\s*([^\s]+pump)/;

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

    function extractDataFromElements(elements) {
        elements.forEach((element) => {
            if (element.textContent.includes("Name:") && element.textContent.includes("GEM)")) {
                const nameMatch = element.textContent.match(nameRegex);
                if (nameMatch) {
                    const name = nameMatch[1].trim();
                    let sibling = element.nextElementSibling;
                    while (sibling) {
                        const contractMatch = sibling.textContent.match(contractRegex);
                        if (contractMatch) {
                            const contractKey = contractMatch[1];
                            const pair = { name, contractKey };
                            if (!nameContractPairs.some(item => item.contractKey === contractKey)) {
                                nameContractPairs.push(pair);
                                console.log(`Name: ${name}, Contract: ${contractKey}`);
                                sendContractPairsToServer(pair);  // Send each pair to the server
                            }
                            break;
                        }
                        sibling = sibling.nextElementSibling;
                    }
                }
            }
        });
    }

    // Initial extraction from existing elements
    const elements = document.querySelectorAll('*');
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
