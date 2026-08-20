#!/usr/bin/env python3
"""Limpa os dados de teste do RLS do site da festa.

Uso:
  python3 limpar-testes.py                (pede email/senha do admin)
  SUPABASE_EMAIL=x SUPABASE_SENHA=y python3 limpar-testes.py
  python3 limpar-testes.py --seco      (nao confirma, apaga tudo de uma vez)

Apaga via API autenticada (conta admin do Supabase):
  - convidados/fotos com nome 'Teste RLS%' ou 'Exp %'
  - arquivos de teste no bucket 'fotos' (prefixo 'teste-')
"""

import json
import os
import sys
import urllib.error
import urllib.request

SUPABASE_URL = 'https://papbvuolghjvzdraaues.supabase.co'
SUPABASE_ANON = ('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.'
                 'eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBhcGJ2dW9sZ2hqdnpkcmFhdWVzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODcyNjEyMTQsImV4cCI6MjEwMjgzNzIxNH0.'
                 '5fpfEI66FTcM5lYYYiyh6DyXXmNNv9b8Z_gBnZALmRk')
NOMES_TESTE = ('Teste RLS', 'Exp ')


def req(method, path, token, body=None, ctype='application/json'):
    data = body if isinstance(body, bytes) else (json.dumps(body).encode() if body is not None else None)
    r = urllib.request.Request(SUPABASE_URL + path, data=data, method=method)
    r.add_header('apikey', SUPABASE_ANON)
    r.add_header('Authorization', 'Bearer ' + token)
    r.add_header('Content-Type', ctype)
    r.add_header('Prefer', 'return=representation')
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def login(email, senha):
    body = json.dumps({'email': email, 'password': senha}).encode()
    r = urllib.request.Request(SUPABASE_URL + '/auth/v1/token?grant_type=password', data=body, method='POST')
    r.add_header('apikey', SUPABASE_ANON)
    r.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except ValueError:
            return e.code, {}


def eh_teste(nome):
    return any(nome.startswith(p) for p in NOMES_TESTE)


def limpar_tabela(token, tabela):
    s, b = req('GET', '/rest/v1/' + tabela + '?select=*', token)
    if s != 200:
        print('  ERRO ao listar ' + tabela + ': status ' + str(s))
        return 0
    linhas = json.loads(b)
    alvo = [r for r in linhas if eh_teste(r.get('nome') or '')]
    for r in alvo:
        s2, _ = req('DELETE', '/rest/v1/' + tabela + '?id=eq.' + str(r['id']), token)
        status = 'ok' if s2 in (200, 204) else ('ERRO ' + str(s2))
        print('  [{:4}] {}.id={} "{}"'.format(status, tabela, r['id'], r['nome']))
    return len(alvo)


def limpar_storage(token):
    s, b = req('POST', '/storage/v1/object/list/fotos', token, {'prefix': '', 'limit': 100, 'offset': 0})
    if s != 200:
        print('  ERRO ao listar storage: status ' + str(s))
        return 0
    objs = json.loads(b)
    alvo = [o for o in objs if o.get('name', '').startswith('teste-')]
    for o in alvo:
        s2, _ = req('DELETE', '/storage/v1/object/fotos/' + o['name'], token)
        status = 'ok' if s2 in (200, 204) else ('ERRO ' + str(s2))
        print('  [{:4}] fotos/{}'.format(status, o['name']))
    return len(alvo)


def main():
    seco = '--seco' in sys.argv
    email = os.environ.get('SUPABASE_EMAIL') or ''
    senha = os.environ.get('SUPABASE_SENHA') or ''
    if not email:
        email = input('Email do admin: ').strip()
    if not senha:
        senha = input('Senha do admin: ')

    print('Entrando no Supabase...')
    s, data = login(email, senha)
    if s != 200 or not data.get('access_token'):
        print('Login falhou: ' + str(data.get('msg') or data.get('error_description') or ('status ' + str(s))))
        sys.exit(1)
    token = data['access_token']
    print('Logado como ' + data.get('user', {}).get('email', email) + '\n')

    if not seco:
        resposta = input('Apagar TODOS os dados de teste (linhas "Teste RLS"/"Exp " e arquivos "teste-*")? [s/N] ')
        if resposta.strip().lower() != 's':
            print('Cancelado.')
            return

    total = 0
    print('Limpando convidados:')
    total += limpar_tabela(token, 'convidados')
    print('Limpando fotos:')
    total += limpar_tabela(token, 'fotos')
    print('Limpando storage:')
    total += limpar_storage(token)

    print('\nRemovidos ' + str(total) + ' itens de teste. Pode rodar `python3 teste-rls.py` para confirmar.')


if __name__ == '__main__':
    main()