from .. import base


class MigrationTests(base.MigrateTestCase):

    def test_migrate_app(self):
        # just check that no exception is raised when calling migrate
        self.makemigrations()
        self.migrate()
