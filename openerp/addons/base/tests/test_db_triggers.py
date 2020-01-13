# coding: utf-8
# Copyright (C) 2019 Levi9 <http://www.levi9.com>
# @author Petar Najman <p.najman@levi9.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import uuid
from openerp.tests import common


class TestBiDbTriggers(common.SavepointCase):
    """Test BI DB Triggers"""

    @classmethod
    def setUpClass(cls):
        super(TestBiDbTriggers, cls).setUpClass()

        cls.name = uuid.uuid4()
        cls.create_date = '2018-10-14 20:15:47.676426'
        cls.write_date = '2015-10-14 20:15:47.676426'

    def test_bi_db_triggers(self):
        """Test DB Triggers"""
        name = uuid.uuid4()

        # Test before insert trigger
        self.env.cr.execute("""
            INSERT INTO ir_model_data (name, module, model, res_id)
            VALUES ('{name}', 'base', '{name}', 1)
            RETURNING id
        """.format(name=name))

        model_data_id = self.env.cr.fetchall()[0][0]

        model_data = self.env['ir.model.data'].browse(model_data_id)
        self.assertIsNotNone(model_data)
        self.assertNotEquals(model_data.create_date, self.create_date)
        self.assertNotEquals(model_data.write_date, self.write_date)

        # Test before update trigger
        self.env.cr.execute("""
            UPDATE ir_model_data 
            SET write_date = '{new_write_date}'
            WHERE id={id}
        """.format(new_write_date=self.write_date, id=model_data.id))

        self.env.invalidate_all()

        self.assertNotEquals(model_data.write_date, self.write_date)

        # Test after delete trigger
        model_data.unlink()

        self.env.cr.execute("""
            SELECT * FROM deleted_records 
            WHERE "table" = 'ir_model_data' AND record_id = {id}
        """.format(id=model_data_id))
        self.assertEquals(len(self.env.cr.fetchall()), 1)
