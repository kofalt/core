import unittest
import json
import csv
import codecs

from sdk_test_case import SdkTestCase
from test_acquisition import create_test_acquisition

import flywheel 
class DataViewTestCases(SdkTestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_view_id = None
        cls.group_id, cls.project_id, cls.session_id, cls.acquisition_id = create_test_acquisition()
        
        # Get user id
        user = cls.fw.get_current_user()
        cls.user_id = user.id

        cls.session = cls.fw.get_session(cls.session_id)
        cls.subject = cls.session.subject

    @classmethod
    def tearDownClass(cls):
        cls.fw_root.delete_project(cls.project_id)
        cls.fw_root.delete_group(cls.group_id)

        if cls.data_view_id:
            cls.fw_root.delete_data_view(cls.data_view_id)

    @classmethod
    def ensure_data_view(cls):
        if cls.data_view_id:
            return

        builder = flywheel.DataViewBuilder('test-data-view')
        builder.column('subject_age')
        builder.column('session.label', dst='session_label')
        builder.column('subject_firstname', dst='firstname')
        builder.column('subject_lastname', dst='lastname')
        builder.include_ids().public()

        cls.data_view_id = cls.fw.add_data_view(cls.user_id, builder.build())

    def test_build_data_view(self):
        fw = self.fw

        # Create the data view
        self.ensure_data_view()

        # Check that we can get the data view back
        self.assertIsNotNone(self.data_view_id)

        r_view = fw.get_data_view(self.data_view_id)
        self.assertIsNotNone(r_view)

        self.assertEqual(r_view.label, 'test-data-view')
        self.assertEqual(len(r_view.columns), 4)

        views = fw.get_data_views(self.user_id)
        self.assertGreaterEqual(len(views), 1)
        self.assertIn(r_view, views)

    def test_execute_data_view(self):
        fw = self.fw

        self.ensure_data_view()

        with fw.read_data_view_data(self.data_view_id, self.project_id) as resp:
            result = json.load(resp)

        self.assertIsNotNone(result)
        self.assertIn('data', result)
        data = result['data']
        self.assertEqual(len(data), 1)

        row = data[0]
        self.assertEqual(row['project'], self.project_id)
        self.assertEqual(row['subject'], self.subject.id)
        self.assertEqual(row['session'], self.session_id)
        self.assertEqual(row['session_label'], self.session.label)
        self.assertEqual(row['subject_age'], self.subject.age)
        self.assertEqual(row['firstname'], self.subject.firstname)
        self.assertEqual(row['lastname'], self.subject.lastname)

    def test_execute_data_view_dataframe(self):
        try: 
            import pandas
        except ImportError:
            print('No pandas, skipping dataframe test!')
            return

        fw = self.fw

        self.ensure_data_view()

        df = fw.read_data_view_data_frame(self.data_view_id, self.project_id)
        self.assertIsNotNone(df)
        self.assertEqual(df['project'][0], self.project_id)
        self.assertEqual(df['subject'][0], self.subject.id)
        self.assertEqual(df['session'][0], self.session_id)
        self.assertEqual(df['subject_age'][0], self.subject.age)


    def test_execute_adhoc_data_view_csv(self):
        view = flywheel.DataViewBuilder(columns=['subject_age', 'subject_sex']).build()

        with self.fw.read_data_view_data(view, self.project_id, format='csv') as resp:
            reader = csv.reader(resp)

            row = next(reader)
            self.assertEqual(len(row), 5)
            self.assertEqual(row, ['project', 'subject', 'session', 'subject_age', 'subject_sex'])

            row = next(reader)
            self.assertEqual(len(row), 5)
            self.assertEqual(row, [self.project_id, self.subject.id, self.session_id, str(self.subject.age), self.subject.sex])


