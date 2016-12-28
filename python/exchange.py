#!/bin/python
from database_client import DatabaseClient
from market_data import L2Depth, Trade, Snapshot

class ExchangeGateway:
    
    class DataMode:
        """
        Bitwise enum of data mode.
        """
        ALL = 7
        ORDER_BOOK_AND_TRADES_ONLY = 6
        SNAPSHOT_ONLY = 1
        ORDER_BOOK_ONLY = 2
        TRADES_ONLY = 4
        
        @classmethod
        def tostring(cls, val):
            for k,v in vars(cls).iteritems():
                if v==val:
                    return k

        @classmethod
        def fromstring(cls, str):
            return getattr(cls, str.upper(), None)
    
    """
    Exchange gateway
    """
    def __init__(self, 
                 api_socket, 
                 db_client=DatabaseClient(), 
                 data_mode=DataMode.ALL):
        """
        Constructor
        :param exchange_name: Exchange name
        :param exchange_api: Exchange API
        :param db_client: Database client
        """
        self.db_client = db_client
        self.api_socket = api_socket
        self.data_mode = data_mode

    @classmethod
    def get_exchange_name(cls):
        """
        Get exchange name
        :return: Exchange name string
        """
        return ''

    @classmethod
    def get_order_book_table_name(cls, exchange, instmt_name):
        """
        Get order book table name
        :param exchange: Exchange name
        :param instmt_name: Instrument name
        """
        return 'exch_' + exchange.lower() + '_' + instmt_name.lower() + '_book'

    @classmethod
    def get_trades_table_name(cls, exchange, instmt_name):
        """
        Get trades table name
        :param exchange: Exchange name
        :param instmt_name: Instrument name
        """
        return 'exch_' + exchange.lower() + '_' + instmt_name.lower() + '_trades'
        
    @classmethod
    def get_snapshot_table_name(cls):
        return 'exchanges_snapshot'
    
    @classmethod
    def init_snapshot_table(cls, data_mode, db_client):
        if data_mode & ExchangeGateway.DataMode.SNAPSHOT_ONLY:
            db_client.create(cls.get_snapshot_table_name(),
                             Snapshot.columns(),
                             Snapshot.types(),
                             [0,1])
                             
    def init_order_book_table(self, instmt):
        if self.data_mode & ExchangeGateway.DataMode.ORDER_BOOK_ONLY:
            table_name = self.get_order_book_table_name(instmt.get_exchange_name(),
                                                        instmt.get_instmt_name())
            self.db_client.create(table_name,
                                  ['id'] + L2Depth.columns(),
                                  ['int'] + L2Depth.types(),
                                  [0])        
                             
    def init_trades_table(self, instmt):
        if self.data_mode & ExchangeGateway.DataMode.TRADES_ONLY:
            table_name = self.get_trades_table_name(instmt.get_exchange_name(),
                                                    instmt.get_instmt_name())
            self.db_client.create(table_name,
                                  ['id'] + Trade.columns(),
                                  ['int'] + Trade.types(),
                                  [0])  

    def get_order_book_init(self, instmt):
        """
        Initialization method in get_order_book
        :param instmt: Instrument
        :return: Last id
        """
        if self.data_mode & ExchangeGateway.DataMode.ORDER_BOOK_ONLY:
            table_name = self.get_order_book_table_name(instmt.get_exchange_name(),
                                                        instmt.get_instmt_name())            
            self.init_order_book_table(instmt)
            ret = self.db_client.select(table_name,
                                        columns=['id'],
                                        orderby='id desc',
                                        limit=1)
            if len(ret) > 0:
                return ret[0][0]
            else:
                return 0
        else:
            return 0

    def get_trades_init(self, instmt):
        """
        Initialization method in get_trades
        :param instmt: Instrument
        :return: Last id
        """
        if self.data_mode & ExchangeGateway.DataMode.TRADES_ONLY:
            table_name = self.get_trades_table_name(instmt.get_exchange_name(),
                                                    instmt.get_instmt_name())            
            self.init_trades_table(instmt)
            id_ret = self.db_client.select(table=table_name,
                                        columns=['id'],
                                        orderby="id desc",
                                        limit=1)
            trade_id_ret = self.db_client.select(table=table_name,
                                           columns=['trade_id'],
                                           orderby="id desc",
                                           limit=1)
    
            if len(id_ret) > 0 and len(trade_id_ret) > 0:
                return id_ret[0][0], trade_id_ret[0][0]
            else:
                return 0, 0
        else:
            return 0, 0
    
    def start(self, instmt):
        """
        Start the exchange gateway
        :param instmt: Instrument
        :return List of threads
        """
        return []

    def insert_order_book(self, instmt):
        """
        Insert order book row into the database client
        :param instmt: Instrument
        """
        if self.data_mode & ExchangeGateway.DataMode.SNAPSHOT_ONLY and \
           instmt.get_l2_depth() is not None and \
           instmt.get_last_trade() is not None:
            self.db_client.insert(table=self.get_snapshot_table_name(),
                                  columns=Snapshot.columns(),
                                  values=Snapshot.values(instmt.get_exchange_name(),
                                                         instmt.get_instmt_name(),
                                                         instmt.get_l2_depth(),
                                                         instmt.get_last_trade(),
                                                         Snapshot.UpdateType.ORDER_BOOK),
                                  is_orreplace=True,
                                  is_commit=not(self.data_mode & ExchangeGateway.DataMode.ORDER_BOOK_ONLY))
            
        if self.data_mode & ExchangeGateway.DataMode.ORDER_BOOK_ONLY:
            self.db_client.insert(table=instmt.get_order_book_table_name(),
                                  columns=['id'] + L2Depth.columns(),
                                  values=[instmt.get_order_book_id()] + instmt.get_l2_depth().values())

    def insert_trade(self, instmt, trade):
        """
        Insert trade row into the database client
        :param instmt: Instrument
        """
        instmt.set_last_trade(trade)

        if self.data_mode & ExchangeGateway.DataMode.SNAPSHOT_ONLY and \
           instmt.get_l2_depth() is not None and \
           instmt.get_last_trade() is not None:
            self.db_client.insert(table=self.get_snapshot_table_name(),
                                  columns=Snapshot.columns(),
                                  values=Snapshot.values(instmt.get_exchange_name(),
                                                         instmt.get_instmt_name(),
                                                         instmt.get_l2_depth(),
                                                         instmt.get_last_trade(),
                                                         Snapshot.UpdateType.TRADES),
                                  is_orreplace=True,
                                  is_commit=not(self.data_mode & ExchangeGateway.DataMode.TRADES_ONLY)) # For testing only
        
        if self.data_mode & ExchangeGateway.DataMode.TRADES_ONLY:
            self.db_client.insert(table=instmt.get_trades_table_name(),
                                  columns=['id']+Trade.columns(),
                                  values=[instmt.get_trade_id()]+trade.values())
