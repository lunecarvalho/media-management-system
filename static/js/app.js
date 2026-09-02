/**
 * MediaTrack - App JavaScript
 * Funcionalidades gerais da aplicação
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Lucide Icons
    if (window.lucide) {
        lucide.createIcons();
    }
    
    // Mobile Menu Toggle
    const menuToggler = document.getElementById('menu-toggler');
    const sidebar = document.getElementById('sidebar');
    
    if (menuToggler && sidebar) {
        menuToggler.addEventListener('click', function() {
            sidebar.classList.toggle('aberto');
        });
        
        // Fechar sidebar ao clicar fora
        document.addEventListener('click', function(event) {
            if (!sidebar.contains(event.target) && !menuToggler.contains(event.target)) {
                sidebar.classList.remove('aberto');
            }
        });
    }
    
    // Fechar mensagens de alerta automaticamente
    const alertas = document.querySelectorAll('.alerta');
    alertas.forEach(function(alerta) {
        if (!alerta.classList.contains('alerta-erro')) {
            setTimeout(function() {
                alerta.style.transition = 'opacity 0.3s ease';
                alerta.style.opacity = '0';
                setTimeout(function() {
                    alerta.remove();
                }, 300);
            }, 5000);
        }
    });
    
    // Atualizar contador de acervo a partir da API
    const contadorAcervo = document.getElementById('contador-acervo');
    if (contadorAcervo) {
        fetch('/api/itens/')
            .then(response => response.json())
            .then(dados => {
                contadorAcervo.textContent = dados.count ?? dados.length ?? '0';
            })
            .catch(error => {
                contadorAcervo.textContent = '0';
            });
    }
    
    // Função auxiliar para formatar data
    window.formatarData = function(data) {
        const opcoes = { 
            year: 'numeric', 
            month: '2-digit', 
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        };
        return new Date(data).toLocaleDateString('pt-BR', opcoes);
    };
    
    // Função auxiliar para moeda brasileira
    window.formatarMoeda = function(valor) {
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL'
        }).format(valor);
    };
    
    // Validação básica de formulários
    const formularios = document.querySelectorAll('form');
    formularios.forEach(function(form) {
        form.addEventListener('submit', function(e) {
            const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');
            let valido = true;
            
            inputs.forEach(function(input) {
                if (!input.value.trim()) {
                    input.style.borderColor = '#ff6b6b';
                    valido = false;
                } else {
                    input.style.borderColor = '';
                }
            });
            
            if (!valido) {
                e.preventDefault();
                alert('Por favor, preenchaa todos os campos obrigatórios.');
            }
        });
    });
    
    console.log('MediaTrack App carregado com sucesso!');
});
