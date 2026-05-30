// Stepper Tab Switcher
function showStep(stepNumber) {
    // Hide all step content
    const contents = document.querySelectorAll('.step-content');
    contents.forEach(content => {
        content.classList.remove('active');
    });

    // Deactivate all step nav items
    const navItems = document.querySelectorAll('.step-nav-item');
    navItems.forEach(item => {
        item.classList.remove('active');
    });

    // Show selected step content
    const activeContent = document.getElementById(`step-${stepNumber}`);
    if (activeContent) {
        activeContent.classList.add('active');
    }

    // Activate selected step nav item
    const activeNavItem = document.querySelectorAll('.step-nav-item')[stepNumber - 1];
    if (activeNavItem) {
        activeNavItem.classList.add('active');
    }
}

// Copy Install Command to Clipboard
function copyInstallCommand() {
    const installInput = document.getElementById('install-cmd');
    const copyBtn = document.getElementById('copy-install-btn');

    installInput.select();
    installInput.setSelectionRange(0, 99999); // For mobile devices

    navigator.clipboard.writeText(installInput.value).then(() => {
        // Change icon to checked success state
        copyBtn.innerHTML = '<i class="fa-solid fa-check" style="color: #10b981;"></i>';
        
        // Restore original icon after 2 seconds
        setTimeout(() => {
            copyBtn.innerHTML = '<i class="fa-regular fa-copy"></i>';
        }, 2000);
    });
}

// Copy Generated CLI Commands to Clipboard
function copyGenCommand(elementId) {
    const commandText = document.getElementById(elementId).innerText;
    
    navigator.clipboard.writeText(commandText).then(() => {
        const block = document.getElementById(elementId).closest('.output-block');
        const copyButton = block.querySelector('.output-header button');
        
        // Change icon to checked success state
        copyButton.innerHTML = '<i class="fa-solid fa-check" style="color: #10b981;"></i>';
        
        // Restore original icon after 2 seconds
        setTimeout(() => {
            copyButton.innerHTML = '<i class="fa-regular fa-copy"></i>';
        }, 2000);
    });
}

// CLI Command Generator Logic
function generateCommands() {
    const backup = document.getElementById('p-backup').value.trim() || 'my_backup.json';
    const chunks = document.getElementById('p-chunks').value.trim() || './rtdb-chunks';
    const node = document.getElementById('p-node').value.trim() || 'users';
    const sa = document.getElementById('p-sa').value.trim() || 'serviceAccountKey.json';

    // Generate Split Command
    document.getElementById('gen-split').innerText = 
        `make split BACKUP=${backup} CHUNKS=${chunks} NODE=${node}`;

    // Generate Validate Command
    document.getElementById('gen-val').innerText = 
        `make validate BACKUP=${backup} CHUNKS=${chunks} NODE=${node}`;

    // Generate Upload Command
    document.getElementById('gen-up').innerText = 
        `make upload CHUNKS=${chunks} SA=${sa} DBPATH=/${node}`;
}

// Initial generation run on load
window.addEventListener('DOMContentLoaded', () => {
    generateCommands();
});
