from lark import Lark, Transformer, v_args
import re
import datetime


class QueryParser:
    # Define the grammar for the query
    query_grammar = """
        ?start: expression

        ?expression: or_expression
        ?or_expression: and_expression
                      | or_expression "or" and_expression -> or_expr

        ?and_expression: not_expression
                       | and_expression "and" not_expression -> and_expr

        ?not_expression: comparison
                       | "not" not_expression -> not_expr

        ?comparison: atom
                   | NAME "==" atom -> eq
                   | NAME "!=" atom -> neq
                   | atom "<" atom -> lt
                   | atom "<=" atom -> le
                   | atom ">" atom -> gt
                   | atom ">=" atom -> ge
                   | atom "<=" atom "<=" atom -> range_inclusive
                   | atom "<" atom "<=" atom -> range_top_inclusive
                   | atom "<=" atom "<" atom -> range_low_inclusive
                   | atom "<" atom "<" atom -> range_not_inclusive
                   | "exists" "(" NAME ")" -> exists
                   | NAME "==" "regexp" "(" STRING ")" -> regexp_match

        ?atom: STRING -> string
             | DATE -> date
             | NAME -> var
             | "(" expression ")"

        %import common.CNAME -> NAME
        %import common.WS
        %import common.ESCAPED_STRING -> STRING

        // Define the DATE pattern as YYYY-MM-DDTHH:MM:SS.sssZ
        DATE: /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z/

        %ignore WS
    """

    @v_args(inline=True)
    class QueryTransformer(Transformer):
        def or_expr(self, left, right):
            return f"({left} or {right})"

        def and_expr(self, left, right):
            return f"({left} and {right})"

        def eq(self, name, value):
            return f"{name} == '{value}'"

        def neq(self, name, value):
            return f"{name} != '{value}'"

        def lt(self, left, right):
            return f"{left} < '{right}'"

        def le(self, left, right):
            return f"{left} <= '{right}'"

        def gt(self, left, right):
            return f"{left} > '{right}'"

        def ge(self, left, right):
            return f"{left} >= '{right}'"

        def range_inclusive(self, lower_bound, var, upper_bound):
            return f"('{lower_bound}' <= {var} <= '{upper_bound}')"

        def range_top_inclusive(self, lower_bound, var, upper_bound):
            return f"('{lower_bound}' < {var} <= '{upper_bound}')"

        def range_low_inclusive(self, lower_bound, var, upper_bound):
            return f"('{lower_bound}' <= {var} < '{upper_bound}')"

        def range_not_inclusive(self, lower_bound, var, upper_bound):
            return f"('{lower_bound}' < {var} < '{upper_bound}')"

        def exists(self, name):
            return f"{name} is not None"

        def regexp_match(self, name, pattern):
            return f"re.search(r{pattern}, {name}) is not None"

        def not_expr(self, expr):
            return f"not ({expr})"

        def string(self, s):
            return s.strip('"')

        def var(self, name):
            return name

        def date(self, d):
            # Convert the date string to a datetime object
            return f"datetime.strptime('{d}', '{self.date_format}')"

    def __init__(self):
        # Initialize the parser with the defined grammar and transformer
        self.parser = Lark(self.query_grammar, parser='lalr', transformer=self.QueryTransformer())

    def parse_query(self, query):
        # Parse and transform the query into a Python expression
        tree = self.parser.parse(query)
        return tree

    def match(self, dictionary, query):
        # Parse the query into a Python expression
        expression = self.parse_query(query)

        # Evaluate the expression in the context of the dictionary
        try:
            # Pass the dictionary directly as the context for eval
            return eval(expression, {"re": re}, dictionary)
        except Exception as e:
            print(f"Error evaluating expression: {e}")
            return False


# # Example usage
# if __name__ == "__main__":
#     query_parser = QueryParser()
#
#     # List of dictionaries to match
#     data = [
#         {'username': 'pippo', 'date': '2023-08-30T12:34:56.123456Z', 'name': 'paperino'},
#         {'username': 'pluto', 'date': '2023-08-29T12:34:56.123456Z', 'name': 'daffy'},
#         {'username': 'clara', 'date': '2023-08-28T12:34:56.123456Z', 'name': None}
#     ]
#
#     # Example query
#     # query = '(username == regexp(".*c.*") and exists(name)) or (username == pippo and 27/08/2024 <= date <= 29/08/2024)'
#     # query = 'username == regexp(".*c.*") and not exists(name)'
#     query = 'username == clara and date > "2023-08-27T12:00:00.000000Z"'
#
#     # Check which dictionaries match the query
#     for item in data:
#         if query_parser.match(item, query):
#             print(f"Matched: {item}")
#         else:
#             print(f"Did not match: {item}")