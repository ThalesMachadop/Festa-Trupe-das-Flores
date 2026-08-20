#!/usr/bin/env python3
"""Teste automatizado do RLS + Storage do Supabase do site da festa.

Uso: python3 teste-rls.py

Checa se a integração Supabase está OK:
- anon pode INSERT/SELECT em convidados e fotos
- anon pode subir arquivo no bucket fotos e ler via URL pública
- anon NÃO pode apagar (DELETE/UPDATE bloqueado por RLS)
"""

import json
import sys
import urllib.error
import urllib.request
import uuid

SUPABASE_URL = 'https://papbvuolghjvzdraaues.supabase.co'
SUPABASE_ANON = ('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.'
                 'eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBhcGJ2dW9sZ2hqdnpkcmFhdWVzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODcyNjEyMTQsImV4cCI6MjEwMjgzNzIxNH0.'
                 '5fpfEI66FTcM5lYYYiyh6DyXXmNNv9b8Z_gBnZALmRk')
TAG = 'teste-' + uuid.uuid4().hex[:8]


def req(method, path, body=None, ctype='application/json'):
    data = body if isinstance(body, bytes) else (json.dumps(body).encode() if body is not None else None)
    r = urllib.request.Request(SUPABASE_URL + path, data=data, method=method)
    r.add_header('apikey', SUPABASE_ANON)
    r.add_header('Authorization', 'Bearer ' + SUPABASE_ANON)
    r.add_header('Content-Type', ctype)
    r.add_header('Prefer', 'return=representation')
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def check(nome, ok, detalhe=''):
    marca = 'PASS' if ok else 'FAIL'
    print('  [{:4}] {} {}'.format(marca, nome, detalhe))
    return ok


def linha_existe(resp_json, ident):
    try:
        rows = json.loads(resp_json)
    except ValueError:
        return False
    return any(r.get('id') == ident for r in rows)


def main():
    print('== Teste RLS do site da festa ==\n')
    todos = []

    s, b = req('POST', '/rest/v1/convidados', {'nome': 'Teste RLS ' + TAG})
    todos.append(check('INSERT convidados (anon)', s in (200, 201), '(status ' + str(s) + ')'))
    if s in (200, 201):
        cid = json.loads(b)[0]['id']
    else:
        cid = None

    s, b = req('GET', '/rest/v1/convidados?select=*')
    todos.append(check('SELECT convidados (anon)', s == 200, '(status ' + str(s) + ')'))

    s, b = req('POST', '/storage/v1/object/fotos/' + TAG + '.txt', b'teste de upload do RLS\n', 'text/plain')
    todos.append(check('UPLOAD no bucket fotos (anon)', s in (200, 201), '(status ' + str(s) + ')'))

    s, b = req('GET', '/storage/v1/object/public/fotos/' + TAG + '.txt')
    todos.append(check('GET da URL publica do arquivo', s == 200, '(status ' + str(s) + ')'))

    url = SUPABASE_URL + '/storage/v1/object/public/fotos/' + TAG + '.txt'
    s, b = req('POST', '/rest/v1/fotos', {'nome': 'Teste RLS', 'descricao': 'teste', 'url': url, 'caminho': TAG + '.txt'})
    todos.append(check('INSERT fotos (anon)', s in (200, 201), '(status ' + str(s) + ')'))
    if s in (200, 201):
        fid = json.loads(b)[0]['id']
    else:
        fid = None

    s, b = req('GET', '/rest/v1/fotos?select=*')
    todos.append(check('SELECT fotos (anon)', s == 200, '(status ' + str(s) + ')'))

    if fid is not None:
        s, b = req('DELETE', '/rest/v1/fotos?id=eq.' + str(fid))
        s2, b2 = req('GET', '/rest/v1/fotos?select=id&id=eq.' + str(fid))
        ficou = linha_existe(b2, fid)
        todos.append(check('DELETE anon bloqueado em fotos', ficou, '(linha ainda existe: ' + str(ficou) + ')'))

    if cid is not None:
        s, b = req('DELETE', '/rest/v1/convidados?id=eq.' + str(cid))
        s2, b2 = req('GET', '/rest/v1/convidados?select=id&id=eq.' + str(cid))
        ficou = linha_existe(b2, cid)
        todos.append(check('DELETE anon bloqueado em convidados', ficou, '(linha ainda existe: ' + str(ficou) + ')'))

    s, b = req('DELETE', '/storage/v1/object/fotos/' + TAG + '.txt')
    todos.append(check('DELETE anon bloqueado no storage', s in (400, 403), '(status ' + str(s) + ')'))

    print('\nResultado: ' + str(sum(todos)) + '/' + str(len(todos)) + ' passaram')
    if cid is not None:
        print('Limpeza pendente (via dashboard, anon nao apaga):')
        print('  - convidados id=' + str(cid))
    if fid is not None:
        print('  - fotos id=' + str(fid))
    print('  - storage fotos/' + TAG + '.txt')
    sys.exit(0 if all(todos) else 1)


if __name__ == '__main__':
    main()