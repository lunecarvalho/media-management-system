from unittest.mock import patch
from io import StringIO
from django.test import SimpleTestCase
from scripts.project_automation import desired_status, discover, run, is_ignored


@patch.dict('os.environ', {'PROJECT_AUTOMATION_ENABLED': 'true'})
class ProjectTests(SimpleTestCase):
    def test_ignored_open_and_closed_inside_and_outside_project(self):
        for state in ('OPEN', 'CLOSED'):
            for current in (None, 'Todo', 'In Progress', 'In Review', 'Done'):
                for apply in (False, True):
                    for selection in (None, 25):
                        with self.subTest(state=state, current=current, apply=apply, selection=selection):
                            api = self.setup_reconciliation(current=current, state=state)
                            issue = {'id': 'issue-test', 'number': 25, 'state': state,
                                     'repository': {'nameWithOwner': 'lunecarvalho/media-management-system'},
                                     'labels': {'nodes': [{'name': 'project-ignore'}], 'pageInfo': {'hasNextPage': False}}}
                            with patch('scripts.project_automation.pages', side_effect=[[], [issue], [], [issue]]), patch('sys.stdout', new_callable=StringIO) as output:
                                run(apply, selection)
                                run(apply, selection)
                            api.assert_not_called()
                            self.assertIn('ignorada: project-ignore', output.getvalue())
                            patch.stopall()

    def test_ignored_issue_does_not_prevent_other_issue_update(self):
        api = self.setup_reconciliation(state='CLOSED')
        def issue(number, labels):
            return {'id': 'issue-test' if number == 25 else 'ignored-test', 'number': number,
                    'state': 'CLOSED', 'repository': {'nameWithOwner': 'lunecarvalho/media-management-system'},
                    'labels': {'nodes': [{'name': label} for label in labels], 'pageInfo': {'hasNextPage': False}}}
        with patch('scripts.project_automation.pages', side_effect=[[], [issue(26, ['project-ignore']), issue(25, ['bug'])]]):
            run(True)
        self.assertEqual(api.call_count, 1)
        self.assertEqual(api.call_args.kwargs['item'], 'item-test')

    def test_ignore_label_on_later_page(self):
        issue = {'id': 'test', 'labels': {'nodes': [{'name': 'bug'}], 'pageInfo': {'hasNextPage': True}}}
        with patch('scripts.project_automation.graphql', side_effect=[
            {'node': {'labels': {'nodes': [{'name': 'bug'}], 'pageInfo': {'hasNextPage': True, 'endCursor': 'cursor-test'}}}},
            {'node': {'labels': {'nodes': [{'name': 'project-ignore'}], 'pageInfo': {'hasNextPage': False}}}},
        ]) as api:
            self.assertTrue(is_ignored(issue))
        self.assertEqual(api.call_args.kwargs['cursor'], 'cursor-test')

    def test_label_name_matches_exactly_case_insensitive(self):
        for name, expected in (('project-ignore', True), ('Project-Ignore', True), ('project-ignore-later', False), ('bug', False)):
            self.assertEqual(is_ignored({'labels': {'nodes': [{'name': name}], 'pageInfo': {'hasNextPage': False}}}), expected)

    def test_removing_label_resumes_normal_reconciliation(self):
        api = self.setup_reconciliation(state='CLOSED')
        issue = {'id': 'issue-test', 'number': 25, 'state': 'CLOSED',
                 'repository': {'nameWithOwner': 'lunecarvalho/media-management-system'},
                 'labels': {'nodes': [{'name': 'project-ignore'}], 'pageInfo': {'hasNextPage': False}}}
        with patch('scripts.project_automation.pages', side_effect=[[], [issue], [], [issue]]):
            run(True, 25)
            api.assert_not_called()
            issue['labels']['nodes'] = []
            run(True, 25)
        self.assertEqual(api.call_count, 1)
        self.assertEqual(api.call_args.kwargs['option'], 'Done')

    def test_missing_label_data_blocks_mutation(self):
        api = self.setup_reconciliation(state='CLOSED')
        with patch('scripts.project_automation.is_ignored', side_effect=RuntimeError('label lookup failed')):
            with self.assertRaises(RuntimeError):
                run(True)
        api.assert_not_called()

    def test_selection_leaves_other_issues_untouched(self):
        api = self.setup_reconciliation(current='Todo', state='CLOSED')
        with patch('scripts.project_automation.pages', side_effect=[[], [
            {'id': 'issue-test', 'number': 25, 'state': 'CLOSED', 'labels': {'nodes': [], 'pageInfo': {'hasNextPage': False}}, 'repository': {'nameWithOwner': 'lunecarvalho/media-management-system'}},
            {'id': 'other-issue', 'number': 26, 'state': 'CLOSED', 'labels': {'nodes': [], 'pageInfo': {'hasNextPage': False}}, 'repository': {'nameWithOwner': 'lunecarvalho/media-management-system'}},
        ]]):
            run(True, 25)
        self.assertEqual(api.call_count, 1)
        self.assertEqual(api.call_args.kwargs['item'], 'item-test')

    def test_native_add_returning_correct_status_needs_no_update(self):
        api = self.setup_reconciliation(current=None)
        api.return_value = {'addProjectV2ItemById': {'item': {
            'id': 'native-item', 'fieldValueByName': {'name': 'Todo'}}}}
        run(True, 25)
        self.assertEqual(api.call_count, 1)
        self.assertIn('addProjectV2ItemById', api.call_args.args[0])

    def setup_reconciliation(self, current='Todo', state='OPEN', repository='lunecarvalho/media-management-system'):
        items = {} if current is None else {'issue-test': {'id': 'item-test', 'status': current}}
        discovery = patch('scripts.project_automation.discover', return_value=(
            'project-test', 'field-test', {n: n for n in ('Todo', 'In Progress', 'In Review', 'Done')}, items))
        pages = patch('scripts.project_automation.pages', side_effect=[[], [
            {'id': 'issue-test', 'number': 25, 'state': state, 'labels': {'nodes': [], 'pageInfo': {'hasNextPage': False}}, 'repository': {'nameWithOwner': repository}}]])
        api = patch('scripts.project_automation.graphql')
        self.addCleanup(patch.stopall)
        discovery.start()
        pages.start()
        return api.start()

    def test_same_status_does_not_mutate(self):
        api = self.setup_reconciliation()
        run(True)
        api.assert_not_called()

    def test_specific_issue(self):
        api = self.setup_reconciliation(current='Todo', state='CLOSED')
        run(True, '25')
        self.assertEqual(api.call_count, 1)
        self.assertEqual(api.call_args.kwargs['item'], 'item-test')

    def test_missing_issue(self):
        api = self.setup_reconciliation()
        with self.assertRaises(RuntimeError):
            run(True, 999)
        api.assert_not_called()

    def test_foreign_issue_rejected(self):
        api = self.setup_reconciliation(repository='other/repo')
        with self.assertRaises(RuntimeError):
            run(True, 25)
        api.assert_not_called()

    def test_invalid_issue_selector(self):
        with patch('scripts.project_automation.graphql') as api:
            for value in ('other/repo#25', '-1', '0', '25; echo secret'):
                with self.assertRaises(RuntimeError):
                    run(False, value)
            api.assert_not_called()

    def test_dry_run_reports_missing_item_without_mutation(self):
        api = self.setup_reconciliation(current=None)
        with patch.dict('os.environ', {'PROJECT_TOKEN': 'read-only-test-sentinel'}), patch('sys.stdout', new_callable=StringIO) as output:
            run(False, 25)
        api.assert_not_called()
        self.assertIn('acao: adicionar', output.getvalue())
        self.assertIn('ausente', output.getvalue())
        self.assertNotIn('read-only-test-sentinel', output.getvalue())

    def test_review_preserved_for_open_issue(self):
        api = self.setup_reconciliation(current='In Review')
        run(True)
        api.assert_not_called()
        self.assertEqual(desired_status('OPEN', True, 'In Review'), 'In Review')

    def test_review_closed_goes_to_done(self):
        api = self.setup_reconciliation(current='In Review', state='CLOSED')
        run(True)
        self.assertEqual(api.call_args.kwargs['option'], 'Done')

    def test_four_write_gate_combinations(self):
        for apply, enabled in ((False, 'false'), (True, 'false'), (False, 'true'), (True, 'true')):
            with self.subTest(apply=apply, enabled=enabled):
                api = self.setup_reconciliation(current='Todo', state='CLOSED')
                with patch.dict('os.environ', {'PROJECT_AUTOMATION_ENABLED': enabled}):
                    if apply and enabled == 'false':
                        with self.assertRaises(RuntimeError):
                            run(apply)
                    else:
                        run(apply)
                self.assertEqual(api.call_count, int(apply and enabled == 'true'))
                patch.stopall()

    @patch('scripts.project_automation.graphql')
    def test_wrong_project_rejected(self, api):
        for change in ({'number': 4}, {'owner': {'login': 'other'}}, {'url': 'https://github.com/users/other/projects/3'}):
            project = {'id': 'test', 'number': 3, 'owner': {'login': 'lunecarvalho'},
                       'url': 'https://github.com/users/lunecarvalho/projects/3'}
            project.update(change)
            api.return_value = {'user': {'projectV2': project}}
            with self.assertRaises(RuntimeError):
                discover()

    @patch('scripts.project_automation.graphql')
    @patch('scripts.project_automation.pages')
    @patch('scripts.project_automation.discover')
    def test_replay_reuses_items_and_only_updates_target(self, discovery, pages, api):
        items = {'issue-existing': {'id': 'item-existing', 'status': 'In Progress'}}
        discovery.return_value = ('project-test', 'status-test', {
            'Todo': 'todo-test', 'In Progress': 'progress-test', 'Done': 'done-test',
        }, items)
        issues = [{'id': 'issue-existing', 'number': 1, 'state': 'OPEN', 'labels': {'nodes': [], 'pageInfo': {'hasNextPage': False}}, 'repository': {'nameWithOwner': 'lunecarvalho/media-management-system'}},
                  {'id': 'issue-new', 'number': 2, 'state': 'CLOSED', 'labels': {'nodes': [], 'pageInfo': {'hasNextPage': False}}, 'repository': {'nameWithOwner': 'lunecarvalho/media-management-system'}}]
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
                         ['item-existing', 'item-new'])

    @patch('scripts.project_automation.pages')
    @patch('scripts.project_automation.graphql')
    def test_discovery_filters_other_repository_and_uses_returned_ids(self, api, pages):
        api.return_value = {'user': {'projectV2': {'id': 'returned-project', 'number': 3, 'url': 'https://github.com/users/lunecarvalho/projects/3', 'owner': {'login': 'lunecarvalho'}, 'fields': {
            'nodes': [{'id': 'returned-field', 'name': 'Status', 'options': [
                {'name': name, 'id': name + '-test'} for name in ('Todo', 'In Progress', 'Done')]}],
            'pageInfo': {'hasNextPage': False}}}}}
        pages.return_value = [
            {'id': 'ours', 'content': {'id': 'issue', 'labels': {'nodes': [], 'pageInfo': {'hasNextPage': False}}, 'repository': {'nameWithOwner': 'lunecarvalho/media-management-system'}}},
            {'id': 'other', 'content': {'id': 'foreign', 'labels': {'nodes': [], 'pageInfo': {'hasNextPage': False}}, 'repository': {'nameWithOwner': 'other/repo'}}},
            {'id': 'draft', 'content': None},
        ]
        project, field, options, items = discover()
        self.assertEqual((project, field), ('returned-project', 'returned-field'))
        self.assertEqual(items, {'issue': {'id': 'ours', 'status': None}})
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
