"""Descobre e reconcilia apenas o Project pessoal #3; sem IDs fixados."""
import argparse
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OWNER = 'lunecarvalho'
PROJECT_NUMBER = 3
PROJECT_URL = 'https://github.com/users/lunecarvalho/projects/3'
REPOSITORY = 'lunecarvalho/media-management-system'


def graphql(query, **variables):
    token = os.environ.get('PROJECT_TOKEN')
    if not token:
        raise RuntimeError('Configure PROJECT_TOKEN com acesso ao Project pessoal.')
    for attempt in range(3):
        req = Request('https://api.github.com/graphql',
            data=json.dumps({'query': query, 'variables': variables}).encode(),
            headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json',
                     'User-Agent': 'MediaTrack-Project-Automation'})
        try:
            with urlopen(req, timeout=30) as response:
                result = json.load(response)
            if result.get('errors'):
                raise RuntimeError('GraphQL retornou erros: confira acesso, limites e esquema.')
            return result['data']
        except (HTTPError, URLError, TimeoutError) as exc:
            if isinstance(exc, HTTPError) and exc.code not in (429, 502, 503, 504):
                raise RuntimeError('GitHub recusou a operação HTTP ' + str(exc.code)) from None
            if attempt == 2:
                raise RuntimeError('GitHub indisponível após três tentativas.') from None
            time.sleep(2 ** attempt)


def pages(query, path, **variables):
    cursor = None
    while True:
        data = graphql(query, cursor=cursor, **variables)
        for key in path:
            data = data[key]
        yield from data['nodes']
        if not data['pageInfo']['hasNextPage']:
            return
        cursor = data['pageInfo']['endCursor']


def discover():
    project = graphql('''query { user(login:"lunecarvalho") { projectV2(number:3) {
      id number url owner { ... on User { login } } fields(first:100) { nodes { ... on ProjectV2SingleSelectField { id name options { id name } } }
      pageInfo { hasNextPage } } } } }''')['user']['projectV2']
    if not project:
        raise RuntimeError('Project #3 inacessível. Nenhum Project será criado.')
    if (project.get('number') != PROJECT_NUMBER or project.get('url') != PROJECT_URL
            or project.get('owner', {}).get('login') != OWNER):
        raise RuntimeError('Project retornado nao corresponde ao destino autorizado.')
    if project['fields']['pageInfo']['hasNextPage']:
        raise RuntimeError('Descoberta incompleta: mais de 100 campos.')
    fields = [f for f in project['fields']['nodes'] if f.get('name') == 'Status']
    if len(fields) != 1:
        raise RuntimeError('É necessário um único campo Status.')
    options = {o['name']: o['id'] for o in fields[0]['options']}
    if not {'Todo', 'In Progress', 'Done'} <= options.keys():
        raise RuntimeError('Confira as opções Todo, In Progress e Done no Project #3.')
    items = list(pages('''query($id:ID!, $cursor:String) { node(id:$id) { ... on ProjectV2 {
      items(first:100,after:$cursor) { nodes { id fieldValueByName(name:"Status") { ... on ProjectV2ItemFieldSingleSelectValue { name optionId } } content { ... on Issue { id number repository { nameWithOwner } } } }
      pageInfo { hasNextPage endCursor } } } } }''', ['node', 'items'], id=project['id']))
    ours = {}
    for item in items:
        content = item.get('content')
        if content and content.get('repository', {}).get('nameWithOwner') == REPOSITORY:
            ours[content['id']] = {'id': item['id'], 'status': (item.get('fieldValueByName') or {}).get('name')}
    print(json.dumps({'owner': OWNER, 'project_number': PROJECT_NUMBER, 'url': project['url'],
                      'repository': REPOSITORY, 'field': 'Status', 'project_id': project['id'],
                      'status_field_id': fields[0]['id'], 'options': options}, ensure_ascii=False))
    return project['id'], fields[0]['id'], options, ours


def desired_status(state, open_pr, current=None):
    if state == 'OPEN' and current == 'In Review':
        return current
    return 'Done' if state == 'CLOSED' else ('In Progress' if open_pr else 'Todo')


def run(apply=False, issue_number=None):
    if os.environ.get('GITHUB_REPOSITORY', REPOSITORY) != REPOSITORY:
        raise RuntimeError('Repositório não autorizado.')
    if apply and os.environ.get('PROJECT_AUTOMATION_ENABLED') != 'true':
        raise RuntimeError('Escrita bloqueada: PROJECT_AUTOMATION_ENABLED deve ser true.')
    if issue_number is not None:
        if not str(issue_number).isascii() or not str(issue_number).isdigit() or int(issue_number) < 1:
            raise RuntimeError('issue_number deve ser um inteiro positivo deste repositorio.')
        issue_number = int(issue_number)
    project, field, options, items = discover()
    open_issues = set()
    for pr in pages('''query($cursor:String) { repository(owner:"lunecarvalho",name:"media-management-system") {
      pullRequests(first:100,after:$cursor,states:OPEN) { nodes {
        closingIssuesReferences(first:100) { nodes { id repository { nameWithOwner } } pageInfo { hasNextPage } }
      } pageInfo { hasNextPage endCursor } } } }''', ['repository', 'pullRequests']):
        refs = pr['closingIssuesReferences']
        if refs['pageInfo']['hasNextPage']:
            raise RuntimeError('Mais de 100 referências em uma PR: operação interrompida.')
        open_issues.update(i['id'] for i in refs['nodes'] if i['repository']['nameWithOwner'] == REPOSITORY)
    issues = list(pages('''query($cursor:String) { repository(owner:"lunecarvalho",name:"media-management-system") {
      issues(first:100,after:$cursor,states:[OPEN,CLOSED]) { nodes { id number state repository { nameWithOwner } }
      pageInfo { hasNextPage endCursor } } } }''', ['repository', 'issues']))
    if any(i.get('repository', {}).get('nameWithOwner') != REPOSITORY for i in issues):
        raise RuntimeError('Issue de repositorio nao autorizado; nenhuma escrita iniciada.')
    if issue_number is not None:
        issues = [i for i in issues if i['number'] == issue_number]
        if len(issues) != 1:
            raise RuntimeError('Issue inexistente neste repositorio; nenhuma escrita iniciada.')
    for issue in issues:
        item = items.get(issue['id'])
        current = item['status'] if item else None
        status = desired_status(issue['state'], issue['id'] in open_issues, current)
        action = 'adicionar' if item is None else ('nenhuma' if current == status else 'atualizar')
        label = current or ('sem Status' if item else 'ausente (nao esta no Project)')
        print(f"Issue #{issue['number']} | estado: {issue['state']} | atual: {label} | desejado: {status} | acao: {action}"
              + (' | In Review manual preservado' if current == status == 'In Review' else ''))
        if not apply or action == 'nenhuma':
            continue
        if item is None:
            result = graphql('''mutation($project:ID!, $issue:ID!) {
              addProjectV2ItemById(input:{projectId:$project,contentId:$issue}) { item { id
                fieldValueByName(name:"Status") { ... on ProjectV2ItemFieldSingleSelectValue { name } }
              } }
            }''', project=project, issue=issue['id'])['addProjectV2ItemById']['item']
            item = {'id': result['id'], 'status': (result.get('fieldValueByName') or {}).get('name')}
            items[issue['id']] = item
            # Auto-add nativo pode ter criado/preenchido o item entre consulta e adicao.
            status = desired_status(issue['state'], issue['id'] in open_issues, item['status'])
            if item['status'] == status:
                continue
        graphql('''mutation($project:ID!, $item:ID!, $field:ID!, $option:String!) {
          updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field,
          value:{singleSelectOptionId:$option}}) { projectV2Item { id } }
        }''', project=project, item=item['id'], field=field, option=options[status])
        item['status'] = status


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--issue-number')
    args = parser.parse_args()
    try:
        run(args.apply, args.issue_number)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
