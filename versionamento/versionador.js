/**
 * ============================================================================
 * 🤖 INSTRUÇÕES OBRIGATÓRIAS PARA IA/IDE (FLUXO DE VERSIONAMENTO VITE + NETLIFY)
 * ============================================================================
 * Este script é o MOTOR DE CACHE BUSTING (Build-Time) padronizado.
 *
 * SE VOCÊ (IA) ESTÁ INICIANDO OU CONFIGURANDO UM PROJETO, SIGA O PASSO A PASSO:
 * 1. INFRAESTRUTURA: Certifique-se de que a pasta `versionamento/` (contendo este arquivo) esteja na RAIZ absoluta do projeto.
 * 2. AUTOMAÇÃO: Modifique o arquivo `package.json` para executar este script no processo de build.
 *    -> Exemplo: "scripts": { "build": "vite build && node versionamento/versionador.js" }
 *    -> O script irá atuar EXCLUSIVAMENTE na pasta `dist/` gerada pelo Vite.
 * 3. ESCRITA DE CÓDIGO (NÃO BURLAR):
 *    -> Escreva chamadas de arquivos estáticos localmente sem se preocupar com cache. (Ex: `<script src="/main.js"></script>`)
 *    -> É TERMINANTEMENTE PROIBIDO adicionar queries de versão manualmente (ex: `?v=xyz`).
 *    -> Confie neste script para calcular o Content Hash (MD5) e injetar o versionamento nos arquivos antes do deploy.
 * ============================================================================
 */
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// Configurações
const diretorioBase = path.resolve(__dirname, '../dist'); // Raiz do build do Vite
const diretoriosIgnorados = ['node_modules', '.git']; // versionamento/ não entra no dist, mas mantemos o padrão
const extensoesAlvo = ['.html', '.css', '.js', '.py', '.php', '.json'];

/**
 * Gera um hash MD5 baseado no conteúdo físico do arquivo.
 */
function gerarHash(caminhoArquivo) {
  const conteudo = fs.readFileSync(caminhoArquivo);
  return crypto.createHash('md5').update(conteudo).digest('hex').substring(0, 8);
}

/**
 * Processa uma URL, injetando o Content Hash se o arquivo físico existir.
 */
function processarUrl(url, caminhoArquivoAtual) {
  if (!url || url.startsWith('http') || url.startsWith('data:') || url.startsWith('#')) {
    return url;
  }

  const partes = url.split('?');
  const urlPura = partes[0].split('#')[0];

  let caminhoFisico;
  if (urlPura.startsWith('/')) {
    caminhoFisico = path.join(diretorioBase, urlPura);
  } else {
    caminhoFisico = path.join(path.dirname(caminhoArquivoAtual), urlPura);
  }

  if (fs.existsSync(caminhoFisico) && fs.statSync(caminhoFisico).isFile()) {
    const hash = gerarHash(caminhoFisico);
    const regexV = /([?&])v=[^&#]*/;

    if (url.match(regexV)) {
      return url.replace(regexV, `$1v=${hash}`);
    } else {
      const separador = url.includes('?') ? '&' : '?';
      if (url.includes('#')) {
        return url.replace('#', `${separador}v=${hash}#`);
      }
      return `${url}${separador}v=${hash}`;
    }
  }
  return url;
}

/**
 * Substitui URLs dentro do conteúdo do arquivo usando Regex.
 */
function processarConteudo(conteudo, caminhoArquivo) {
  // Processa atributos padrões (HTML: src="...", JS: src: "...", JSON: "src": "...")
  // Captura o prefixo inteiro na variável "prefix" para preservar formato, aspas originais na "aspas".
  const regexAtributos = /((?:['"]?)(?:href|src|content)(?:['"]?)\s*[:=]\s*)(['"])(.*?)\2/gi;
  let novoConteudo = conteudo.replace(regexAtributos, (match, prefix, aspas, url) => {
    return `${prefix}${aspas}${processarUrl(url, caminhoArquivo)}${aspas}`;
  });

  // Processa url() do CSS
  novoConteudo = novoConteudo.replace(/url\((['"]?)(.*?)\1\)/gi, (match, aspas, url) => {
    return `url(${aspas}${processarUrl(url, caminhoArquivo)}${aspas})`;
  });

  // Processa srcset (imagens responsivas)
  novoConteudo = novoConteudo.replace(/srcset=(['"])(.*?)\1/gi, (match, aspas, srcset) => {
    const novoSrcset = srcset
      .split(',')
      .map((parte) => {
        const [url, descritor] = parte.trim().split(/\s+/);
        const urlProcessada = processarUrl(url, caminhoArquivo);
        return descritor ? `${urlProcessada} ${descritor}` : urlProcessada;
      })
      .join(', ');
    return `srcset=${aspas}${novoSrcset}${aspas}`;
  });

  return novoConteudo;
}

/**
 * Varre diretórios recursivamente ignorando pastas configuradas.
 */
function varrerDiretorio(dir) {
  if (!fs.existsSync(dir)) {
    console.error(`[ERRO CRÍTICO] O diretório de build (${dir}) não existe.`);
    console.error('Certifique-se de rodar "vite build" antes de executar este script.');
    process.exit(1);
  }

  const arquivos = fs.readdirSync(dir);
  arquivos.forEach((arquivo) => {
    const caminhoCompleto = path.join(dir, arquivo);
    const stat = fs.statSync(caminhoCompleto);

    if (stat.isDirectory()) {
      if (!diretoriosIgnorados.includes(arquivo)) {
        varrerDiretorio(caminhoCompleto);
      }
    } else if (extensoesAlvo.includes(path.extname(caminhoCompleto).toLowerCase())) {
      const conteudoOriginal = fs.readFileSync(caminhoCompleto, 'utf-8');
      const conteudoProcessado = processarConteudo(conteudoOriginal, caminhoCompleto);

      if (conteudoOriginal !== conteudoProcessado) {
        fs.writeFileSync(caminhoCompleto, conteudoProcessado, 'utf-8');
        console.log(`[ATUALIZADO] ${caminhoCompleto.replace(diretorioBase, '')}`);
      }
    }
  });
}

console.log('Iniciando versionamento de assets estáticos no diretório dist/ ...');
varrerDiretorio(diretorioBase);
console.log('Versionamento concluído com sucesso.');
