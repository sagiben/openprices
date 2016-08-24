import logging
from enum import Enum
from sqlalchemy import create_engine, or_, and_, not_
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy import Column, Integer, BigInteger, String, ForeignKey, Date, DECIMAL, Text,\
    exists, UniqueConstraint
from sqlalchemy.orm import sessionmaker, relationship, backref
from sqlalchemy.types import Enum as SqlEnum
from sqlalchemy.inspection import inspect
from datetime import datetime

Base = declarative_base()

class StoreType(Enum):
    physical = 1
    web = 2
    both = 3

class Unit(Enum):
    """
    Unit type enum
    """
    unknown = 0
    kg = 1
    gr = 2
    liter = 3
    ml = 4
    unit = 5
    m = 6  # Meter

    @staticmethod
    def to_unit(unit_str):
        """
        convert string to Unit enum value
        Args:
            unit_str:

        Returns:

        """
        str_dict = {
            Unit.kg: ['קג', 'קילוגרם', 'קילוגרמים', 'ק"ג'],
            Unit.gr: ['גר', 'גרמים', "גר'"],
            Unit.liter: ['ליטר', 'ליטרים', "ל'"],
            Unit.ml: ['מ"ל', 'מיליליטרים', 'מיליליטר', 'מל'],
            Unit.unit: ['יחידה'],
            Unit.m: ['מטר', 'מטרים', 'מ', "מ'"]
        }
        try:
            unit_str = unit_str.strip()
        except AttributeError:
            unit_str = ''
        for unit_type, unit_type_strings in str_dict.items():
            if any(s == unit_str for s in unit_type_strings):
                return unit_type.value
        return Unit.unknown.value


class Chain(Base):
    __tablename__ = 'chains'

    id = Column(Integer, primary_key=True, autoincrement=True)
    full_id = Column(BigInteger, nullable=False)
    subchain_id = Column(Integer, default=0)
    name = Column(String)

    UniqueConstraint(full_id, subchain_id)

    stores = relationship("Store", backref='chain')  # one to many
    web_access = relationship('ChainWebAccess', backref='chain', uselist=False)  # one to one

    def __repr__(self):
        return self.name


class ChainWebAccess(Base):
    __tablename__ = 'web_access'

    chain_id = Column(Integer, ForeignKey(Chain.id), primary_key=True)
    url = Column(String)
    username = Column(String, default='')
    password = Column(String, default='')


class Store(Base):
    __tablename__ = 'stores'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    store_id = Column(Integer)
    chain_id = Column(Integer, ForeignKey(Chain.id))
    name = Column(String)
    city = Column(String)
    address = Column(String, default='')
    type = Column(SqlEnum(StoreType))
    UniqueConstraint(store_id, chain_id)

    # current_prices = relationship("CurrentPrice", backref='store')
    # prices_history = relationship("PriceHistory", backref='store')

    def __repr__(self):
        # return '{:03}: {}'.format(self.store_id, self.name)
        return '{}-{}:{}'.format(self.chain.name, self.name, self.address)

    def __eq__(self, other):
        # must be different for different  chain-store combination because of the UniqueConstraint
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)


class Item(Base):
    __tablename__ = 'items'

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    code = Column(String)
    quantity = Column(DECIMAL(precision=2))
    unit = Column(SqlEnum(Unit))

    store_products = relationship('StoreProducts', backref='item', lazy='joined')

    def __repr__(self):
        return '{}: {}'.format(self.name, self.id)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.id == other.id


class StoreProducts(Base):
    __tablename__ = 'store_products'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    item_id = Column(BigInteger, ForeignKey(Item.id))
    store_id = Column(BigInteger, ForeignKey(Store.id))
    internal_id = Column(BigInteger, default=None)  # TODO need default?
    name = Column(Text)
    # saving the quantity/unit_qty for cases that auto parsing don't work, to allow manual parsing
    quantity = Column(Text)
    unit_quantity = Column(Text)

    current_prices = relationship("CurrentPrice", backref='store_products')
    prices_history = relationship("PriceHistory", backref='store_products')


class PriceHistory(Base):
    __tablename__ = 'price_history'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    store_product_id = Column(BigInteger, ForeignKey(StoreProducts.id))
    start_date = Column(Date, default=datetime.today, index=True)
    end_date = Column(Date, default=datetime.today, index=True)

    UniqueConstraint(start_date, store_product_id)

class CurrentPrice(Base):
    __tablename__ = 'current_price'

    store_product_id = Column(BigInteger, ForeignKey(StoreProducts.id))
    price = Column(DECIMAL(precision=2), primary_key=True)


class Promotions(Base):
    __tablename__ = 'promotions'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    store_id = Column(BigInteger, ForeignKey(Store.id))
    internal_promotion_code = Column(BigInteger)
    description = Column(Text)
    start_date = Column(Date, default=datetime.date)
    end_date = Column(Date, default=datetime.date)
    UniqueConstraint(store_id, internal_promotion_code)

    items = relationship('PromotionItems', backref='promotion', lazy='joined')
    restrictions = relationship('Restrictions', backref='promotion', lazy='joined')
    price_func = relationship('PriceFunction', backref='promotion')


class PromotionItems(Base):
    __tablename__ = 'promotion_items'

    promotion_id = Column(BigInteger, ForeignKey(Promotions.id), primary_key=True)
    item_id = Column(BigInteger, ForeignKey(Item.id), primary_key=True)


class RestrictionType(Enum):
    min_qty = 1
    max_qty = 2
    basket_price = 3
    club_ids = 4
    specific_item = 5


class Restrictions(Base):
    __tablename__  = 'restrictions'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    promotion_id = Column(BigInteger, ForeignKey(Promotions.id), index=True)
    restriction_type = Column(SqlEnum(RestrictionType))
    amount = Column(Integer, default=None)
    item_id = Column(BigInteger, ForeignKey(Item.id), nullable=True)


class PriceFunctionType(Enum):
    total_price = 1
    percentage = 2


class PriceFunction(Base):
    __tablename__ = 'price_functions'

    promotion_id = Column(BigInteger, ForeignKey(Promotions.id), primary_key=True)
    function_type = Column(SqlEnum(PriceFunctionType))
    value = Column(DECIMAL(precision=2))


sqlite = 'sqlite:///shopping.db'
postgres = 'postgresql+psycopg2://test:123@localhost:5432/shop'

db = sqlite
class SessionController(object):
    """
    This is the DB access interface
    """
    def __init__(self, db_path=db, db_logging=False, logger=None):
        logging.basicConfig(level=logging.INFO)
        self.logger = logger or logging.getLogger(__name__)
        self.logger.info('connecting to DB')
        self.engine = create_engine(db_path, echo=db_logging)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        Base.metadata.create_all(self.engine)
        self.logger.info('DB connected')

    def get_session(self):
        return self.session

    def query(self, model):
        """
        Get a
        Args:
            model:

        Returns:

        """
        return self.session.query(model)

    def exists(self, obj_field, value):
        (ret, ), = self.session.query(exists().where(obj_field == value))
        return ret

    def exists_where_list(self, obj_fields, values):
        return self.session.query(exists().where(and_(*[field == value for field, value in zip(obj_fields, values)]))).scalar()

    def key(self, model):
        return inspect(model).primary_key

    def bulk_insert(self, objects):
        self.session.bulk_save_objects(objects)

    def bulk_update(self, mapper, mappings):
        self.session.bulk_update_mapping(mapper, mappings)

    def commit(self):
        """
        Commit changes to the DB
        Returns:

        """
        self.logger.info('Committing to db')
        try:
            self.session.commit()
        except Exception:
            self.logger.exception('Commit to DB failed')
            self.session.rollback()
            return False
        self.logger.info('Commit ended successfully')
        return True

    def update(self, model, update_dict):
        """
        session.query(Stuff).update({Stuff.foo: Stuff.foo + 1})
        :param model:
        :param update_dict:
        :return:
        """
        self.session.query(model).update(update_dict)

    def add(self, model):
        return self.session.add(model)

    def get(self, model, **kwargs):
        instance = self.query(model).filter_by(**kwargs).first()
        if instance:
            return instance

    def get_or_create(self, model, **kwargs):
        instance = self.query(model).filter_by(**kwargs).first()
        if instance:
            return instance
        else:
            instance = model(**kwargs)
            self.add(instance)
            self.commit()
            return instance

    def instance_key(self, cls, instance):
        return [getattr(instance, key.name) for key in self.key(cls)]

    def exists_in_db(self, cls, instance):
        """
        check if the instance with same key(s) exists in DB
        Args:
            cls:
            instance:

        Returns:

        """
        exist_dict = {}
        for key in self.key(cls):
            exist_dict[key.name] = getattr(instance, key.name)

        q = self.query(cls)
        for field, value in exist_dict.items():
            q = q.filter(getattr(cls, field).like(value))
        return q.all()

    def _drop_table(self, model):
        self.logger.info('Dropping table {}'.format(model.__table__))
        model.__table__.drop(self.engine)

    def filter_or(self, query, conditions):
        return query.filter(or_(*conditions))

    def filter_and(self, query, conditions):
        return query.filter(and_(*conditions))

    def filter_in(self, query, column, lst):
        """

        Args:
            query:
            column:
            lst:

        Returns:

        """
        return query.filter(column.in_(lst))

    def filter_condition(self, model, cond):
        return self.query(model).filter(cond)

def main():
    engine = create_engine('sqlite:///sql_interface_test.db', echo=True)
    Session = sessionmaker(bind=engine)
    session = Session()
    Base.metadata.create_all(engine)

            # print(session.query(Chain).get(Chains_ids[Chain]))
    # for item in items.values():
    #     session.add(Item(item.code, item.Chain, item))
    session.commit()

if __name__ == '__main__':
    main()