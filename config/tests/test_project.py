from unittest.mock import patch
from django.test import SimpleTestCase
from scripts.project_automation import desired_status, discover, run


class ProjectTests(SimpleTestCase):
    @patch('scripts.project_automation.graphql')
    @patch('scripts.project_automation.pages')
    @patch('scripts.project_automation.discover')
    def test_replay_reuses_items_and_only_updates_target(self, discovery, pages, api):
        items = {'issue-existing': 'item-existing'}
        discovery.return_value = ('project-test', 'status-test', {
            'Todo': 'todo-test', 'In Progress': 'progress-test', 'Done': 'done-test',
        }, items)
        issues = [{'id': 'issue-existing', 'number': 1, 'state': 'OPEN'},
                  {'id': 'issue-new', 'number': 2, 'state': 'CLOSED'}]
        pages.side_effect = [[], issues, [], issues]
        api.return_value = {'addProjectV2ItemById': {'item': {'id': 'item-new'}}}
        run(True)
        run(True)
        additions = [c for c in api.call_args_list if 'addProjectV2ItemById' in c.args[0]]
        self.assertEqual(len(additions), 1)
        self.assertEqual(additions[0].kwargs['issue'], 'issue-new')
        self.assertTrue(all(c.kwargs['project'] == 'project-test' for c in api.call_args_list))
        updates = [c for c in api.call_args_list if 'updateProjectV2ItemFieldValue' in c.args[0]]
        self.assertEqual([c.kwargs['item'] for c in updates],
                         ['item-existing', 'item-new', 'item-existing', 'item-new'])

    @patch('scripts.project_automation.pages')
    @patch('scripts.project_automation.graphql')
    def test_discovery_filters_other_repository_and_uses_returned_ids(self, api, pages):
        api.return_value = {'user': {'projectV2': {'id': 'returned-project', 'fields': {
            'nodes': [{'id': 'returned-field', 'name': 'Status', 'options': [
                {'name': name, 'id': name + '-test'} for name in ('Todo', 'In Progress', 'Done')]}],
            'pageInfo': {'hasNextPage': False}}}}}
        pages.return_value = [
            {'id': 'ours', 'content': {'id': 'issue', 'repository': {'nameWithOwner': 'lunecarvalho/media-management-system'}}},
            {'id': 'other', 'content': {'id': 'foreign', 'repository': {'nameWithOwner': 'other/repo'}}},
            {'id': 'draft', 'content': None},
        ]
        project, field, options, items = discover()
        self.assertEqual((project, field), ('returned-project', 'returned-field'))
        self.assertEqual(items, {'issue': 'ours'})
        self.assertEqual(options['Todo'], 'Todo-test')

    def test_lifecycle(self):
        self.assertEqual(desired_status('CLOSED', True), 'Done')
        self.assertEqual(desired_status('OPEN', True), 'In Progress')
        self.assertEqual(desired_status('OPEN', False), 'Todo')

    @patch('scripts.project_automation.graphql')
    def test_missing_project_fails_without_mutations(self, api):
        api.return_value = {'user': {'projectV2': None}}
        with self.assertRaises(RuntimeError):
            discover()
        self.assertEqual(api.call_count, 1)

    @patch.dict('os.environ', {'GITHUB_REPOSITORY': 'other/repo'})
    @patch('scripts.project_automation.graphql')
    def test_other_repository_untouched(self, api):
        with self.assertRaises(RuntimeError):
            run(True)
        api.assert_not_called()
