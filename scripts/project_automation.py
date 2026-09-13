"""Descobre e reconcilia apenas o Project pessoal #3; sem IDs fixados."""
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
      id fields(first:100) { nodes { ... on ProjectV2SingleSelectField { id name options { id name } } }
      pageInfo { hasNextPage } } } } }''')['user']['projectV2']
    if not project:
        raise RuntimeError('Project #3 inacessível. Nenhum Project será criado.')
    if project['fields']['pageInfo']['hasNextPage']:
        raise RuntimeError('Descoberta incompleta: mais de 100 campos.')
    fields = [f for f in project['fields']['nodes'] if f.get('name') == 'Status']
    if len(fields) != 1:
        raise RuntimeError('É necessário um único campo Status.')
    options = {o['name']: o['id'] for o in fields[0]['options']}
    if not {'Todo', 'In Progress', 'Done'} <= options.keys():
        raise RuntimeError('Confira as opções Todo, In Progress e Done no Project #3.')
    items = list(pages('''query($id:ID!, $cursor:String) { node(id:$id) { ... on ProjectV2 {
      items(first:100,after:$cursor) { nodes { id content { ... on Issue { id number repository { nameWithOwner } } } }
      pageInfo { hasNextPage endCursor } } } } }''', ['node', 'items'], id=project['id']))
    ours = {i['content']['id']: i['id'] for i in items if i.get('content') and
            i['content'].get('repository', {}).get('nameWithOwner') == REPOSITORY}
    print(json.dumps({'project_id': project['id'], 'status_field_id': fields[0]['id'],
                      'options': options, 'issue_items': ours}))
    return project['id'], fields[0]['id'], options, ours


def desired_status(state, open_pr):
    return 'Done' if state == 'CLOSED' else ('In Progress' if open_pr else 'Todo')


def run(apply=False):
    if os.environ.get('GITHUB_REPOSITORY', REPOSITORY) != REPOSITORY:
        raise RuntimeError('Repositório não autorizado.')
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
      issues(first:100,after:$cursor,states:[OPEN,CLOSED]) { nodes { id number state }
      pageInfo { hasNextPage endCursor } } } }''', ['repository', 'issues']))
    for issue in issues:
        status = desired_status(issue['state'], issue['id'] in open_issues)
        print('Issue #' + str(issue['number']) + ': ' + status)
        if not apply:
            continue
        item = items.get(issue['id'])
        if item is None:
            item = graphql('''mutation($project:ID!, $issue:ID!) {
              addProjectV2ItemById(input:{projectId:$project,contentId:$issue}) { item { id } }
            }''', project=project, issue=issue['id'])['addProjectV2ItemById']['item']['id']
            items[issue['id']] = item
        graphql('''mutation($project:ID!, $item:ID!, $field:ID!, $option:String!) {
          updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field,
          value:{singleSelectOptionId:$option}}) { projectV2Item { id } }
        }''', project=project, item=item, field=field, option=options[status])


if __name__ == '__main__':
    try:
        run('--apply' in sys.argv)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
