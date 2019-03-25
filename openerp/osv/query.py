# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2010 OpenERP S.A. http://www.openerp.com
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from copy import deepcopy



def _quote(to_quote):
    if '"' not in to_quote:
        return '"%s"' % to_quote
    return to_quote


class Query(object):
    """
     Dumb implementation of a Query object, using 3 string lists so far
     for backwards compatibility with the (table, where_clause, where_params) previously used.

     TODO: To be improved after v6.0 to rewrite part of the ORM and add support for:
      - auto-generated multiple table aliases
      - multiple joins to the same table with different conditions
      - dynamic right-hand-side values in domains  (e.g. a.name = a.description)
      - etc.
    """

    def __init__(self, tables=None, where_clause=None, where_clause_params=None, joins=None):

        # holds the list of tables joined using default JOIN.
        # the table names are stored double-quoted (backwards compatibility)
        self.tables = tables or []

        # holds the list of WHERE clause elements, to be joined with
        # 'AND' when generating the final query
        self.where_clause = where_clause or []

        # holds the parameters for the formatting of `where_clause`, to be
        # passed to psycopg's execute method.
        self.where_clause_params = where_clause_params or []

        # holds table joins done explicitly, supporting outer joins. The JOIN
        # condition should not be in `where_clause`. The dict is used as follows:
        #   self.joins = {
        #                    'table_a': [
        #                                  ('table_b', 'table_a_col1', 'table_b_col', 'LEFT JOIN'),
        #                                  ('table_c', 'table_a_col2', 'table_c_col', 'LEFT JOIN'),
        #                                  ('table_d', 'table_a_col3', 'table_d_col', 'JOIN'),
        #                               ]
        #                 }
        #   which should lead to the following SQL:
        #       SELECT ... FROM "table_a" LEFT JOIN "table_b" ON ("table_a"."table_a_col1" = "table_b"."table_b_col")
        #                                 LEFT JOIN "table_c" ON ("table_a"."table_a_col2" = "table_c"."table_c_col")
        self.joins = joins or {}

    def _get_table_aliases(self):
        from openerp.osv.expression import get_alias_from_query
        return [get_alias_from_query(from_statement)[1] for from_statement in self.tables]

    def _get_alias_mapping(self):
        from openerp.osv.expression import get_alias_from_query
        mapping = {}
        for table in self.tables:
            alias, statement = get_alias_from_query(table)
            mapping[statement] = table
        return mapping

    def add_join(self, connection, implicit=True, outer=False):
        """ Join a destination table to the current table.

            :param implicit: False if the join is an explicit join. This allows
                to fall back on the previous implementation of ``join`` before
                OpenERP 7.0. It therefore adds the JOIN specified in ``connection``
                If True, the join is done implicitely, by adding the table alias
                in the from clause and the join condition in the where clause
                of the query. Implicit joins do not handle outer parameter.
            :param connection: a tuple ``(lhs, table, lhs_col, col, link)``.
                The join corresponds to the SQL equivalent of::

                (lhs.lhs_col = table.col)

                Note that all connection elements are strings. Please refer to expression.py for more details about joins.

            :param outer: True if a LEFT OUTER JOIN should be used, if possible
                      (no promotion to OUTER JOIN is supported in case the JOIN
                      was already present in the query, as for the moment
                      implicit INNER JOINs are only connected from NON-NULL
                      columns so it would not be correct (e.g. for
                      ``_inherits`` or when a domain criterion explicitly
                      adds filtering)
        """
        from openerp.osv.expression import generate_table_alias
        (lhs, table, lhs_col, col, link) = connection
        alias, alias_statement = generate_table_alias(lhs, [(table, link)])

        if implicit:
            if alias_statement not in self.tables:
                self.tables.append(alias_statement)
                condition = '("%s"."%s" = "%s"."%s")' % (lhs, lhs_col, alias, col)
                self.where_clause.append(condition)
            else:
                # already joined
                pass
            return alias, alias_statement
        else:
            aliases = self._get_table_aliases()
            assert lhs in aliases, "Left-hand-side table %s must already be part of the query tables %s!" % (lhs, str(self.tables))
            if alias_statement in self.tables:
                # already joined, must ignore (promotion to outer and multiple joins not supported yet)
                pass
            else:
                # add JOIN
                self.tables.append(alias_statement)
                self.joins.setdefault(lhs, []).append((alias, lhs_col, col, outer and 'LEFT JOIN' or 'JOIN'))
            return alias, alias_statement

    def get_sql(self):
        """ Returns (query_from, query_where, query_params). """
        from openerp.osv.expression import get_alias_from_query
        query_from = ''
        tables_to_process = list(self.tables)
        alias_mapping = self._get_alias_mapping()

        def add_joins_for_table(table, query_from):
            for (dest_table, lhs_col, col, join) in self.joins.get(table, []):
                query_from += ' %s %s ON ("%s"."%s" = "%s"."%s")' % \
                    (join, alias_mapping[dest_table], table, lhs_col, dest_table, col)
                query_from = add_joins_for_table(dest_table, query_from)
            return query_from

        joined_aliases = [
            join[0]
            for joined_table in self.joins.values()
            for join in joined_table]
        pos = 0
        for table in tables_to_process:
            table_alias = get_alias_from_query(table)[1]
            if table_alias in joined_aliases:
                continue
            if pos > 0:
                query_from += ','
            pos += 1
            query_from += table
            if table_alias in self.joins:
                query_from = add_joins_for_table(table_alias, query_from)
        return query_from, " AND ".join(self.where_clause), self.where_clause_params

    def __str__(self):
        return '<osv.Query: "SELECT ... FROM %s WHERE %s" with params: %r>' % self.get_sql()

    def append(self, query):
        """ Include another query into self """
        self.where_clause += query.where_clause
        self.where_clause_params += query.where_clause_params
        for table in query.tables:
            if table not in self.tables:
                self.tables.append(table)
        for join_table in query.joins:
            self.joins.setdefault(join_table, [])
            for join in query.joins[join_table]:
                if join not in self.joins[join_table]:
                    self.joins[join_table].append(join)

    def __add__(self, query):
        """ Return a new copy of `self` that includes `query` """
        result = Query(
            list(self.tables or []),
            list(self.where_clause or []),
            list(self.where_clause_params or []),
            deepcopy(self.joins or {}))
        result.append(query)
        return result

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
