#!/usr/bin/env python3
import requests, json, os, base64, glob, hashlib, traceback, getpass, argparse, re;

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad,unpad

#   autor nao importa cara!!!
#   cyberframework.com.br
#   nao.importa.web@xmpp.jp
#   Toda GAMBIARRA eu posso pois o código é meu
#   COMEÇA LENDO O MÉTODO MAIN QUE ESTÁ NO FINAL DO ARQUIVO.

key = None;
MAX_OP = 10; # Número máximo de download (arquivos) por requisição

class Util:
    @staticmethod
    def encrypt(raw, key):
        raw = pad(raw.encode(),16)
        cipher = AES.new(key.encode('utf-8'), AES.MODE_ECB)
        return base64.b64encode(cipher.encrypt(raw))
    @staticmethod
    def encryptbinary(raw, key):
        raw = pad(raw,16)
        cipher = AES.new(key.encode('utf-8'), AES.MODE_ECB)
        return base64.b64encode(cipher.encrypt(raw))
    @staticmethod
    def decrypt(enc, key):
        enc = base64.b64decode(enc)
        cipher = AES.new(key.encode('utf-8'), AES.MODE_ECB)
        return unpad(cipher.decrypt(enc),16)
    @staticmethod
    def md5(fname):
        if not os.path.exists(fname):
            return "";
        hash_md5 = hashlib.md5()
        with open(fname, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

class Server:
    def __init__(self, url, key):
        self.url_service = url;
        self.key = key;

    def post(self, url, data_raw):
        global key;
        data = Util.encrypt(data_raw, self.key);

        retorno = requests.post(self.url_service + url, data = data, headers= {'Content-Type': 'text/plain'});
        return Util.decrypt(  retorno.text, self.key ).decode('utf-8');

class Project:
    def __init__(self, name, path_project, server):
        global key;
        self.name = Util.encrypt(name, key).decode('utf-8');
        self.path_project = path_project;
        self.server = server;
        self.files = [];

    # Limpa a lista de arquivos, usado quando queremos limpar tudo e iniciar subindo novamente os arquivos 
    #       como estão, é uma forma de forçar uma nova versão toda como está em seu computador
    def flush(self): 
        self.files = [];
    
    # Atualiza a lista de arquivos que tem lá no servidor em um arquivo JSON com todos os arquivos, isso fica na
    #       memória, então não é presistido em lugar nenhum.
    def listdir(self):
        self.files = []; self.commits = [];

        return_list = self.server.post("list.php",  json.dumps({"cypher_version" : "1", "action_version" : "1", "project" : self.name}));
        
        # Se não existe nada lá no servidor, ou seja, nem o projeto (quando é novo projeto)
        #    ele retorna True e não coloca nada como commits nem files.
        if return_list == None or json.loads(   return_list   ) ['files'] == None:
            return True;

        # Exibe como output o numero de arquivos e quantos comits foram realizados
        print("Files:\t\t" , len(json.loads(   return_list   ) ['files']));
        print("Commits\t\t", len(json.loads(   return_list   ) ['commits']));
        
        # Atualzia as variaveis em memória com o que vem do servidor
        self.files = json.loads(   return_list   ) ['files'];
        self.commits = json.loads(   return_list   ) ['commits'];

        return True;
    
    #  Busca a versão atual do arquivo no servidor, e extrai dele as informações de versão e MD5
    #       é utilizado para depois comprar se o arquivo local é diferente do arquivo remoto por MD5
    def info_file(self, file_name):
        global key;
        envelop = json.dumps({"cypher_version" : "1", "action_version" : "1", "project" : self.name, "name" : file_name });
        request_result = json.loads( self.server.post("info_file.php", envelop )  );
        return request_result;

    # Download em sí de um arquivo único e específico
    def download_file(self, file_name, version=""):
        global key;
        
        envelop = json.dumps({"cypher_version" : "1", "action_version" : "1", "project" : self.name, "name" : file_name, "version" : version });
        request_result = json.loads( self.server.post("download_file.php", envelop )  );
        
        name_file = Util.decrypt( json.loads(request_result['info'])['name'] , key   ).decode('utf-8');
        buffer_name = self.path_project + "/" + name_file; # No servidor não se pode guardar info de diretório da máquina do programador
                                                           #         e nem no cliente guardar path completo de servidor, então tem que dar um join
        buffer_path = buffer_name[:buffer_name.rfind("/")];# Tendo o diretório completo (fullpath) do arquivo na maquina do cliente
                                                           #         então temos que pegar o diretório 
        
        # se no local não existe os diretórios, então vamos criar os diretórios para depois salvar o arquivo.
        if not os.path.exists(buffer_path):
            os.makedirs(buffer_path, exist_ok=True)
        
        # a escrita/leitura dos arquivos é no formato binário.
        with open(buffer_name, "wb") as f:
            f.write( Util.decrypt(    request_result['content'], key   ) );
            f.close()
        
        return  request_result["status"] == "1"; 
    
    # Download de uma lista de arquivos.
    def download_files(self, elements):
        global key;

        #se não tem arquivos, pula fora
        if elements == None or len(elements) == 0:
            return True;

        envelop = json.dumps({"cypher_version" : "1", "action_version" : "1", "project" : self.name, "files" : elements });
        request_result = json.loads( self.server.post("download_files.php", envelop )  );
        
        # Laço de repetição nos arquivos
        for i in range( len(request_result['files']) ):
            
            # Decripta o nome do arquivo, todos os nomese de arquivos no servidor estão criptografados
            #    nem o nome dos diretórios, lã n o server os arquivos ficam em lista, nem em árvore ficam para
            #    nao expor a estrutura do projeto.
            name_file = Util.decrypt( json.loads(request_result['files'][i]['info'])['name'] , key   ).decode('utf-8');
            buffer_name = self.path_project + "/" + name_file;   # junta como path do projeto
            buffer_path = buffer_name[:buffer_name.rfind("/")];  # pega o diretório.

            if not os.path.exists(buffer_path):
                os.makedirs(buffer_path, exist_ok=True)
            
            # tanto leitura quanto escrita estão no formato binário
            with open(buffer_name, "wb") as f:
                f.write( Util.decrypt(    request_result['files'][i]['content'], key   ) );
                f.close()
        return  request_result["status"] == "1"; 

    # A idẽia do revert é voltar um envio (upload) d o projeto que foi feito no passado, geralmente usado quando fazemos cagada
    #    e não percebemos imediatamente, então podemos voltar um commit anterior, ou muito anterior.
    def revert(self):

        # busca a lista de arquivos que estão diferentes. Não podemos deixar passar, o usuáŕio deve remover os aruqivos
        #     pois se o cver fizer isso e a pessoa não gostar depois, nao tem como encher nosso saco por um erro dele.
        files_diff = self.changed_files();
        if len(files_diff) > 0:
            print();
            #print('\033[93mWARNING:\033[93mExiste arquivos alterados no seu computador e por isso não será feito o revert, faça o UPLOAD de tudo para depois realizar o REVERT');
            print('\033[93mWARNING: \033[93mYou have changed some files since your last upload that have not yet been uploaded. You must upload it before you do \033[96mrevert\033[0m.');
            print();
            return;

        # se passou podemos então baixar a lista de commits e exibir na tela
        #      NUMERO - DESCRIÇÃO DO COMMIT
        # temos que perguntar qual o numero do commit
        self.commit_list();
        print()
        postion_commit = input('Provide the number id of the commit you want to revert: ');
        print()
        
        # limpa tudo, tudo mesmo, pode ter coisas que não estao na lista, DEIXAR O DIRETÓRIO ZERO BALA
        os.system("rm -r " + self.path_project + "/*");
        
        # Baixa a lista de arquiso baseado no commit esecolhido, e traz uma lista de arquivos.
        self.files = self.commits[int(postion_commit) - 1]['files'];
        for i in range(len(self.files)):
            # Decripta o nome do arquivo
            filename = Util.decrypt( self.files[i]['name'] , key   ).decode('utf-8');
            if filename[0:1] == '.': # as vezes o PHP retorna . e .. como diretórios, tem também os diretorios/arquivos .ALGUMACOISA
                continue;

            # testa se o MD5 do servidor bate com o MD5 do local (caso tenha)
            if Util.encrypt(  Util.md5(self.path_project + "/" + filename), key).decode('utf-8') == self.files[i]['md5']:
                continue;

            # ou o MD5 é diferente, ou não existe o arquivo no local. Baixar então com download.
            print("Donwload", "("+ str(i) +"/"+ str(len(self.files)) +")", filename);

            # Arquivo por arquivo download
            self.download_file(self.files[i]['name'], self.files[i]['version'] );

    # Inicia o download, este é o método que é invocado
    def download(self):
        global MAX_OP;

        # Busca uma lista de arquivos que está diferente do local (existe tanto no servidor quanto no local)
        files_diff = self.changed_files();
        if len(files_diff) > 0:
            # exibie uma lista, vai que o cara fez algum código, esqueceu e para nao jogar seu trabalho fora, então vamos mostrar para ele.
            for i in range(len(files_diff)):
                print("Arquivo: ", Util.decrypt( files_diff[i]['name'] , key   ).decode('utf-8'));
            # se ele mesmo vendo que tem arquivos alterados no cliente, e deseja continaur, conta e risco dele.
            if input('This download may override unsaved local changes. Are you sure you want to continue? [y/N]') != 'y':
                return;            
        
        # Legal, ele vai continuar o download
        files_for_download = [];

        # antes de pedir o arquivo, vamos fazer uma lista do que precisa, vamos testar tudo no cliente pois está tudo criptografado
        #   e o servidor nunca, nunca pode saber a chave de descriptografia.
        for i in range(len(self.files)):
            # O nome está criptografado
            filename = Util.decrypt( self.files[i]['name'] , key   ).decode('utf-8');
            # if filename[0:1] == '.': # arquivos ocultos nao quero saber
            #     continue;

            # pega o MD5 tanto do arquivo no servidor quanto no arquivo local, se o MD5 for igual então nao foi alterado
            if Util.encrypt(  Util.md5(self.path_project + "/" + filename), key).decode('utf-8') == self.files[i]['md5']: # file modif
                continue;

            # o script vai baixar, no máximo, a quantidade de arquivos especificada por MAX_OP
            # então, aqui vamos adicionar ao array somente os arquivos que estiverem dentro deste limite
            # especificado. Ao final, baixamos o array inteiro
            if i < MAX_OP:
                files_for_download.append({"name" : self.files[i]['name'], "version" : self.files[i]['version']});
                print("Downloading: ", str(i) +"/"+ str(len(self.files)), filename);

                # se for o último arquivo, para o loop e baixa tudo
                if i == len(self.files) - 1:
                    break;
                else:
                    continue;
            
            break;
        
        if len(files_for_download) > 0:
            self.download_files( files_for_download );
            print('Download completed!');
        else:
            print("Everything already updated.");
                
        return True;
    
    # Pega a definição dos arquivos do servidor e compara com os arquivos local, retorna um array de tudo que está diferente server<>local
    #    repare que o arquivo existe tanto no servidor quanto no cliente.
    def changed_files(self):
        files_diff = [];
        for i in range(len(self.files)):
            filename = Util.decrypt( self.files[i]['name'] , key   ).decode('utf-8');
            if filename[0:1] == '.': # ignora aruivos ocultos
                continue;
            if not os.path.exists(self.path_project + "/" + filename): # arquivo tem que existir tanto no server quanto no local
                continue;
            if Util.encrypt(  Util.md5(self.path_project + "/" + filename), key).decode('utf-8') == self.files[i]['md5']: # tem que ser diferente
                continue;
            files_diff.append(self.files[i]);
        return files_diff;

    def upload_file(self, file_name, path_file_local):
        global key;

        # abre o arquivo para leitura no formato bytes
        with open(path_file_local, 'rb') as f:

            # encripta o nome, temos que esconder o nome. No servidor até o nome dos arquivos são criptografados
            file_name = Util.encrypt(file_name, key).decode('utf-8');
            data_binary = f.read(); # leia os bytes do arquivo local

            # criptografa o conteũdo do arquivo
            content = Util.encryptbinary(data_binary, key).decode('utf-8');

            # tem que tirar um MD5 do arquivo, e adivinha, criptografa até o MD5, afinal isso pode ser uma prova contra você
            md5_file = Util.encrypt(hashlib.md5(data_binary).hexdigest(), key).decode('utf-8');
            
            # vamos pegar as info do arquivo, um arquivo possui muitas versões
            info_server_file = self.info_file(file_name) ;
            for version in info_server_file['info']['versions']:
                if version['md5'] == md5_file: # se teemos uma versão compatível entre o cliente e o servidor, por que fazer upload?
                    return {"status" : 1, "version" : version['name'], "name" : file_name }; # vamos retornar dizendo que estã tudo OK. FORÇA UM RETORNO COMPATIVEL COM O RETORNO DO FINAL DESTE MÉTODO.
            
            # Não foi possível localizar nenhuma versão, então faz o UPLOAD REALMENTE.
            envelop = json.dumps({"cypher_version" : "1", "action_version" : "1", "project" : self.name, "name" : file_name, "content" : content, "md5" : md5_file });
            request_result = self.server.post("upload_file.php",envelop );

            # cria um retorno JSON.
            return {"status" : json.loads( request_result  )["status"], "version" : json.loads( request_result  )["version"], "name" : file_name} ; 
    
    # Faz o envio de 1 arquivo, um único arquivo para commit
    def commit(self, commit):
        global key;

        envelop = json.dumps({"cypher_version" : "1", "action_version" : "1", "project" : self.name,  "commit" : commit });
        request_result = json.loads( self.server.post("commit.php", envelop )  );
        return request_result;
    
    # Lista de commits, printa na tela do cara para ele ver.
    def commit_list(self):
        print()
        for i in range(len(self.commits)):
            print('- \033[96m\033[1m'+ str(i + 1) +'\033[0m', "\t"   , self.commits[i]['name'][4:6] + "/" + self.commits[i]['name'][2:4] + "/" + self.commits[i]['name'][0:2] + " " +  self.commits[i]['name'][6:8] + ":" + self.commits[i]['name'][8:10] , "\t", Util.decrypt( self.commits[i]['comment'], key   ).decode('utf-8'));
    
        print()
    
    # faz uma lista recursiva de diretórios e arquivos, tem que ser em LISTA, ou seja N níveis para 1 nível apenas.
    #    no servidor não podemos guardar a estrutura da ãrvore de arquivos, por isso lá no servidor guardamos em lista
    #    e o nome dos arquivos sao criptografados.
    def list_directory_recursiv(self, path_root, path_list):
        # só inclui arquivos não ignorados pelo .cverignore
        resultado = [];
        ignore_rules = [];
        
        # vai abrir o .cverignore caso ele exista
        if os.path.exists(path_root + '/.cverignore'):
            cverignore = open(path_root + '/.cverignore', 'r');
            paths_to_ignore = cverignore.read().split("\n");

            # com base no .cverignore, gera regras com regex
            for path in paths_to_ignore:
                # se for um diretório, * é usado para ignorar ele recursivamente
                # caso contrário, simplesmente ignora o arquivo
                if os.path.isdir(path_root + '/' + path):
                    ignore_rules.append(path_root + '/' + path + '/.*');
                else:
                    ignore_rules.append(path_root + '/' + path);

        files = os.listdir(path_list);
        for file_name in files:
            path_file_name = path_list + "/" + file_name;
            ignore_file = False;

            # checa se o nome do arquivo bate com alguma das regras do .cverignore
            for rule in ignore_rules:
                ignore_file = bool(re.search(f"^{rule}$", path_file_name));

                # para imediatamente caso uma regra seja encontrada
                if ignore_file:
                    break;
            
            # se este arquivo tiver de ser ignorado, passa para o próximo
            if ignore_file:
                continue;

            if os.path.isdir(path_file_name):
                resultado = resultado + self.list_directory_recursiv(path_root, path_file_name);
            else:
                resultado.append(path_file_name);
        
        return resultado;

    # Método chamado pelo Menu do usuário
    def upload(self, comment=""):

        # Pode ter comentário, pode, mas também pode ir sem comentário.
        #    se tiver comentário tem que criptografar o comentário, lembre-se, criptografamos até a ALMA DO PROGRAMADOR
        if comment != "":
            comment = Util.encrypt(comment, key).decode('utf-8');

        # um envelope para o commit, que vamos preencher com arquivos.
        commit_file = {"message" :  comment, "files" : []};

        # Uma lista de arquivos, uma busca recursiva em todo o sistema de arquivos do projeto.
        buffer_files_local = self.list_directory_recursiv(self.path_project, self.path_project);

        for i in range(len(buffer_files_local)):
            # Pega o nome do arquivo, e fazer o MD5 do conteúdo do arquivo.
            filename = buffer_files_local[i];
            local_file_md5 = Util.encrypt( Util.md5(filename), key).decode('utf-8');

            # tirar o path do projeto do nome do arquivo, pois o filename é o caminho completo da raiz até a extensão
            filename_clear = filename[ len(self.path_project) + 1 :  ];

            # vamos criptografar o nome do arquivo, para nao deixar o nome visível
            filename_crypto = Util.encrypt(filename_clear, key).decode('utf-8');

            # self.files é um array que possui todos os arquivos, se é None, então nao iniciamos o repositório está vazio no server.
            #    agora se é diferente de None, vamos localizar no servidor qual arquivo é o arquivo local, por isso o lambda
            if self.files != None:
                find_elements = [x for x in self.files if x['name'] == filename_crypto];
                # Se tem lá e cá, confirma o MD5, se for igual, nem vamos aidiconar na lista de Upload.
                if len(find_elements) > 0:
                    if find_elements[0]['md5'] == local_file_md5:
                        commit_file['files'].append({"name" : find_elements[0]['name'], "version" : find_elements[0]['version'], "md5" : local_file_md5 });
                        continue;
            
            # exibe na tela o arrquivo que será enviado....
            print("Upload: ", "("+ str(i + 1) +"/"+ str(len(buffer_files_local)) +")", filename_clear);

            # faz o upload do arquivo propriamente dito, recupera o detalhe para saber se status = 1, se sim, sucesso, se nao, falha.
            details = self.upload_file(filename_clear, filename);
            if details['status'] != 1:
                print("Falha ao enviar versao");
                return;
            # os scuessos vamos aidcionando emuma outra lista, a lista do commit. Esta lista também será enviada no final
            #   com todos os sucuessos, em caso de falha de 1 envio, não vai chegar neste ponto.
            commit_file['files'].append({"name" : details['name'], "version" : details['version'], "md5" : local_file_md5 });

        # o envio do commit, que vai registrar os arquivos enviados, lembre-se que tudo é criptografado.
        self.commit(commit_file);

        # Lista o diretório do servidor, para chancelar o que fofi enviado.
        self.listdir();

def print_banner():
    print(':\'######::\'##::::\'##:\'########:\'########::');
    print('\'##... ##: ##:::: ##: ##.....:: ##.... ##:');
    print(' ##:::..:: ##:::: ##: ##::::::: ##:::: ##:');
    print(' ##::::::: ##:::: ##: ######::: ########::');
    print(' ##:::::::. ##:: ##:: ##...:::: ##.. ##:::');
    print(' ##::: ##::. ## ##::: ##::::::: ##::. ##::');
    print('. ######::::. ###:::: ########: ##:::. ##:');
    print(':......::::::...:::::........::..:::::..:: v1.0');
    print('')
    print('')

def non_interactive_mode(args):
    global key, MAX_OP;
    config = None;

    print()

    # força a especificar local_password caso o subcomando não seja "configure"
    if args.subcommands != 'configure' and key == None:

        # é possivel passar a chave local de criptografia como argumento no comando 
        # usando -p ou --local-password, mas diminui a segurança.
        # fiz isso apenas para ter uma forma de especificar a chave ao fazer o download 
        # de arquivos via bash script, foi uma necessidade daquele que escreveu
        if args.local_password != None:
            key = args.local_password;
        else:
            key = getpass.getpass('Local encryption key (1-16): ');
        
        key = key[:16].rjust(16, '-');

    if not os.path.exists( os.path.expanduser("~/.cver.json") ) and args.subcommands != 'configure':
        print('Failed to find configuration file. Use "cver configure" to generate it.');
        return;

    config = json.loads( open(os.path.expanduser("~/.cver.json"), 'r').read() );

    if args.subcommands == 'configure':
        if os.path.exists( os.path.expanduser("~/.cver.json") ):
            if not args.replace:
                print('Configuration file already exists. If you want to replace it, provide --replace');
                return;

        server_addr = args.address;
        server_key = args.key;
        config = {
            "server": "http://"+ server_addr +"/cryptoversion/version/", 
            "key": server_key
        };
        with open(os.path.expanduser("~/.cver.json"), 'w') as f:
            f.write( json.dumps(config) );
    
        return;

    if args.subcommands == 'get':
        project_name = args.project_name;
        project_path = args.project_path;
        MAX_OP = 100 if args.max_operations == None else int(args.max_operations);

        if project_path == None:
            project_path = os.getcwd() + '/' + project_name;
        
        if project_path[-1:] == "/":
            project_path = project_path[0:-1];

        project = Project(project_name, project_path, Server(config['server'], config['key']));
        project.listdir();
        print(f"Downloading project to {project_path} ...")
        project.download();

def setup():
    print_banner();
    config = None;
    if not os.path.exists( os.path.expanduser("~/.cver.json") ):
        while True:
            server_addr = None;
            key = None;

            while True:
                server_addr = input('Server address/domain (without protocol): ');  # informar o domínio, exemplo: exemplo.com..br
                if server_addr == '':
                    print();
                    print('\033[93mThe server\'s address cannot be empty\033[0m');
                else:
                    break;
            
            while True:
                key = input('Server encryption key: '); # informar uma chave comum de criptografia entre o servidor e o cliente.
                if key == '':
                        print('\033[93mThe server\'s encryption key cannot be empty\033[0m');
                        print();
                else:
                    key = key[:16].rjust(16, '-'); # a chave tem 16 caracteres, se nao tiver, temos que criar caracteres extra.
                    break;

            config = {"server" : "http://"+ server_addr +"/cryptoversion/version/", "key" : key};
            # print("\t\033[96m\033[1m\n\tServer: " +  server_addr +  "\n\tKey: \033[0m", key);
            print()
            if input('Are you sure all is correct? [y/N]: ') == 'y':
                with open(os.path.expanduser("~/.cver.json"), 'w') as f:
                    f.write( json.dumps(config) );
                    break;
            else:
                print();
                print("\033[91mTo continue, you must provide and confirm your server's address and it's encryption key.\033[0m");
                print();
                exit();
    else:
        config = json.loads( open(os.path.expanduser("~/.cver.json"), 'r').read() );
    
    os.system('clear');
    return config;

def main(args):
    global key, MAX_OP;
    proj = None;

    # foi usado algum subcomando
    if args.subcommands:
        non_interactive_mode(args);
        return;
    
    os.system('clear');
    # temos que criar/carregar um arquivo de configuração
    config = setup();
    if config == None:
        print("Failed to find configuration file.");
        return;

    # a configuração inicial vai limpar o banner quando concluída, por isso chamamos ele de novo aqui
    print_banner();
    
    #OBTER O PASSWORD da SEGUNDA CRIPTOGRAFIA, ou seja:
    #   1 - criptografa os arquivos: somente voce sabe
    #   2 - criptografa a criptografia dos arquivos: tanto o cliente quanto o servidor possuem essa informação
    key = getpass.getpass('Local encryption key (1-16): ')
    #key = input('Password key (1-16): ');
    key = key[:16].rjust(16, '-');
    
    while True:
        try:
            # Criando um MENU de opções para o usuário.
            print("--------//-------------");
            if proj != None:
                print("\t\t\033[94m\033[1m", Util.decrypt( proj.name, key).decode('utf-8'), '\t', proj.path_project, '\033[0m');
            print("\033[95mload:\033[0m\t\tload a project");
            print("\033[95mlist:\033[0m\t\tupdate the local list of files");
            print("\033[95mupload:\033[0m\t\tupload changed files to the server");
            print("\033[95mdownload:\033[0m\tdownload files from the loaded project");
            print("\033[95mcommits:\033[0m\tlist all commits of the loaded project");
            print("\033[95mrevert:\033[0m\t\trevert a specific commit on the loaded project");
            print("-------------------------------");
            print("\033[96mclear:\033[0m\t\tclear terminal");
            print("\033[96m\033[1mexit:\033[0m\t\texit cver");
            print();
            op = input('> ');

            if(op == 'load'):
                print();
                print('\033[96mProvide the information below to load an existing project or create a new one:\033[0m');
                print();
                name_project = input('Project name: \033[0m');
                path_project = input('Project root path (default: ' + os.getcwd() + '): ');
                print()
                if path_project == "":
                    path_project = os.getcwd() + '/';
                if path_project[-1:] == "/":
                    path_project = path_project[0:-1];
                
                if not os.path.exists(path_project):
                    os.makedirs(path_project);

                proj = Project(name_project, path_project, Server( config['server'], config['key']));
                proj.listdir();
                continue;
            if(op == 'clone'):
                proj.clone();
                continue;
            if(op == 'upload'):
                print()
                comment = input('Leave a comment (default ""): ');
                if comment == None: 
                    comment = "";
                proj.upload(comment);
                continue;
            if(op == 'download'):
                print();
                MAX_OP = int( input('Maximum per operation: \033[0m') );
                print();
                proj.download();
                continue;
            if(op == 'list'):
                proj.listdir();
                continue;
            if(op == 'commits'):
                proj.commit_list();
                continue;
            if(op == 'flush'):
                proj.flush();
                continue;
            if(op == 'revert'):
                proj.revert();
                continue;
            if(op == 'exit'):
                break;
            if(op == 'clear'):
                os.system('clear')
                continue;
                
        except:
            traceback.print_exc();
            
# precisava de uma versão não interativa para usar em um bash script. 
# como eu só precisava fazer download de projetos, criei apenas o subcomando get para 
# baixar e o configure para realizar a configuração inicial.
# futuramente pode ser adicionado subcomandos para o resto das funcionalidades

parser = argparse.ArgumentParser();

# argumento para passar a chave local de criptografia.
# se não especificado, o código irá iniciar um prompt pedindo pela chave (mais seguro).
# para não quebrar a regra de não persistência da chave local de criptografia, esta deverá ser 
# incluida toda vez que rodar um comando no modo não-interativo, com excessão do comando "configure"
parser.add_argument('-p', '--local-password', dest='local_password');

subparsers = parser.add_subparsers(dest='subcommands');

# subcomandos
parser_get = subparsers.add_parser('get');
parser_configure = subparsers.add_parser('configure');

# argumentos dos subcomandos

# configure
parser_configure.add_argument('--address', help='Server\'s address/domain (without protocol)', required=True);
parser_configure.add_argument('--key', help='Server\'s encryption key', required=True);
parser_configure.add_argument('--replace', help='Replace existing configuration file', action="store_true");

# get
parser_get.add_argument('project_name');
parser_get.add_argument('project_path', nargs="?");
parser_get.add_argument('--max-op', help="Determines max operations for downloading files", dest="max_operations")

# parsing
args = parser.parse_args();

main(args);
